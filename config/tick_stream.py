"""Shared, bounded WebSocket tick fanout. No trading operations."""
import asyncio
import hmac
import json
import time
from contextlib import asynccontextmanager, suppress

import rpyc
from fastapi import WebSocket, WebSocketDisconnect


def read_ticks(symbols):
    conn = rpyc.classic.connect("127.0.0.1", 18812)
    try:
        conn._config["sync_request_timeout"] = 5
        # One remote operation serializes the entire batch in Wine.
        code = (
            "(lambda m: {'connected': bool(m.terminal_info() and m.terminal_info().connected), "
            "'ticks': {s: (dict(t._asdict()) if t and t.time else None) "
            "for s in " + repr(symbols) + " if m.symbol_select(s, True) "
            "for t in [m.symbol_info_tick(s)]}})(__import__('MetaTrader5'))"
        )
        return json.loads(str(conn.eval("__import__('json').dumps(" + code + ")")))
    finally:
        conn.close()


class TickHub:
    def __init__(self):
        self.clients = {}
        self.cache = {}

    def offer(self, queue, message):
        if queue.full():
            # Slow clients receive the most recent events, never unbounded history.
            queue.get_nowait()
        queue.put_nowait(message)

    async def run(self):
        heartbeat = 0
        previous_status = None
        while True:
            symbols = sorted(set().union(*(c["symbols"] for c in self.clients.values())))
            if symbols:
                try:
                    batch = await asyncio.to_thread(read_ticks, symbols)
                    connected = batch["connected"]
                    ticks = batch["ticks"] if connected else {}
                except Exception:
                    connected, ticks = False, {}
                if connected != previous_status:
                    self.cache.clear()
                    for queue in self.clients:
                        self.offer(queue, {"type": "status", "mt5_connected": connected})
                    previous_status = connected
                for symbol in symbols:
                    tick = ticks.get(symbol)
                    event = {"type": "tick", "symbol": symbol, **tick} if tick else {
                        "type": "error", "symbol": symbol,
                        "detail": "Symbol unavailable or no tick received" if connected else "MT5 broker connection unavailable",
                    }
                    if self.cache.get(symbol) != event:
                        self.cache[symbol] = event
                        for queue, client in list(self.clients.items()):
                            if symbol in client["symbols"]:
                                self.offer(queue, event)
                self.cache = {s: v for s, v in self.cache.items() if s in symbols}
            if not symbols:
                self.cache.clear()
                previous_status = None
            if time.monotonic() - heartbeat >= 15:
                for queue in list(self.clients):
                    self.offer(queue, {"type": "heartbeat", "server_time": time.time()})
                heartbeat = time.monotonic()
            await asyncio.sleep(1.0)


hub = TickHub()


@asynccontextmanager
async def stream_lifespan(app):
    task = asyncio.create_task(hub.run())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


async def stream_ticks(ws: WebSocket, api_key: str):
    # Never put credentials in URLs, where proxies and history may log them.
    await ws.accept()
    sender = None
    queue = asyncio.Queue(maxsize=64)
    try:
        key = ws.headers.get("x-api-key", "")
        if api_key and not hmac.compare_digest(key, api_key):
            await ws.send_json({"type": "auth_required", "timeout_seconds": 10})
            try:
                auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
            except (ValueError, asyncio.TimeoutError):
                await ws.close(code=4401, reason="Authentication required")
                return
            key = auth.get("api_key", "") if isinstance(auth, dict) and auth.get("action") == "auth" else ""
            if not isinstance(key, str) or not hmac.compare_digest(key, api_key):
                await ws.close(code=4403, reason="Invalid API key")
                return
        if len(hub.clients) >= 100:
            await ws.close(code=4429, reason="Too many clients")
            return
        hub.clients[queue] = {"symbols": set()}
        await ws.send_json({"type": "ready", "max_symbols": 20, "poll_interval_ms": 1000, "symbols": []})

        async def send():
            while True:
                await asyncio.wait_for(ws.send_json(await queue.get()), timeout=10)

        sender = asyncio.create_task(send())
        while True:
            receiver = asyncio.create_task(ws.receive_text())
            done, _ = await asyncio.wait({receiver, sender}, return_when=asyncio.FIRST_COMPLETED)
            if sender in done:
                receiver.cancel()
                with suppress(asyncio.CancelledError):
                    await receiver
                break
            raw = receiver.result()
            if len(raw) > 8192:
                await ws.close(code=1009, reason="Message too large")
                break
            try:
                message = json.loads(raw)
                if not isinstance(message, dict):
                    raise ValueError()
            except ValueError:
                hub.offer(queue, {"type": "error", "detail": "Expected a JSON object"})
                continue
            action = message.get("action")
            if action == "ping":
                hub.offer(queue, {"type": "pong", "server_time": time.time()})
                continue
            symbols = message.get("symbols")
            if action not in ("subscribe", "unsubscribe") or not isinstance(symbols, list) or not symbols or len(symbols) > 20 or any(
                not isinstance(s, str) or not 1 <= len(s) <= 128 for s in symbols
            ):
                hub.offer(queue, {"type": "error", "detail": "Use subscribe/unsubscribe with 1–20 symbol names, or ping"})
                continue
            current = hub.clients[queue]["symbols"]
            updated = current | set(symbols) if action == "subscribe" else current - set(symbols)
            global_symbols = set().union(*(c["symbols"] for q, c in hub.clients.items() if q is not queue)) | updated
            if len(updated) > 20 or len(global_symbols) > 100:
                hub.offer(queue, {"type": "error", "detail": "Subscription limit exceeded"})
                continue
            hub.clients[queue]["symbols"] = updated
            hub.offer(queue, {"type": "subscribed" if action == "subscribe" else "unsubscribed", "symbols": sorted(updated)})
            if action == "subscribe":
                for symbol in symbols:
                    if symbol in hub.cache:
                        hub.offer(queue, hub.cache[symbol])
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        hub.clients.pop(queue, None)
        if sender is not None:
            sender.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await sender


PROTOCOL = {
    "endpoint": "/ws/ticks",
    "transport": "Use wss:// on the public HTTPS domain; do not send API keys over plain ws://.",
    "authentication": {
        "server_clients": "Set X-API-Key in the WebSocket handshake.",
        "browser_clients": {"action": "auth", "api_key": "YOUR_API_KEY"},
        "timeout_seconds": 10,
        "warning": "Never embed a privileged API key in publicly shipped frontend code. Use a trusted backend for public apps. URL query keys are not supported.",
    },
    "commands": [
        {"action": "subscribe", "symbols": ["XAUUSD", "EURUSD"]},
        {"action": "unsubscribe", "symbols": ["EURUSD"]},
        {"action": "ping"},
    ],
    "events": ["auth_required", "ready", "subscribed", "unsubscribed", "tick", "status", "heartbeat", "pong", "error"],
    "tick_example": {"type": "tick", "symbol": "XAUUSD", "time": 1792476380, "time_msc": 1792476380657,
                     "bid": 4145.36, "ask": 4145.48, "last": 0.0, "volume": 0, "flags": 6, "volume_real": 0.0},
    "default_symbols": [],
    "suggested_symbol": "XAUUSD",
    "limits": {"symbols_per_client": 20, "symbols_total": 100, "clients": 100, "poll_interval_ms": 1000, "heartbeat_seconds": 15},
    "delivery": "Shared polling of the latest MT5 tick; not every broker tick is guaranteed. No replay. Slow-client queues discard older events. After reconnect, authenticate and subscribe again with backoff.",
    "timestamps": "Broker-terminal timestamps are forwarded unchanged; heartbeat server_time is Unix time in seconds.",
    "close_codes": {"4401": "Authentication timeout", "4403": "Invalid API key", "4429": "Capacity exceeded", "1009": "Message too large"},
}
