#!/usr/bin/env python3
import hmac
import json
import os
import re
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from typing import Literal, Optional

import rpyc
import uvicorn
from fastapi import Body, Depends, FastAPI, HTTPException, Security, WebSocket
from tick_stream import PROTOCOL, stream_lifespan, stream_ticks
from fastapi.security import APIKeyHeader
from fastapi.openapi.docs import get_swagger_ui_html
from docs_theme import themed
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse
from candle_history import candle_response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


API_KEY = os.environ.get("API_KEY", "")
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: Optional[str] = Security(api_key_header)):
    if API_KEY and not hmac.compare_digest(key or "", API_KEY):
        raise HTTPException(status_code=403, detail="Invalid or missing API Key")


class ErrorResponse(BaseModel):
    detail: str


class HealthResponse(BaseModel):
    status: Literal["healthy", "unhealthy", "error"]
    mt5_connected: bool
    build: Optional[int] = None
    account_logged_in: bool = False
    detail: Optional[str] = None


class IndexResponse(BaseModel):
    service: str
    health: str
    docs: str


class AccountResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    login: int
    server: str
    currency: str
    balance: float
    equity: float
    margin: float
    margin_free: float
    leverage: int
    trade_allowed: bool


class CandleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"symbol": "XAUUSD", "timeframe": "H1", "date_from": "2026-10-01T00:00:00Z", "date_to": "2026-10-19T23:59:59Z", "count": 500, "include_current": False},
        {"symbol": "XAUUSD", "timeframe": "M1"},
        {"symbol": "XAUUSD", "timeframe": "M5", "count": 100, "offset": 100, "order": "desc"}
    ]})
    symbol: str = Field(min_length=1, max_length=128, description="Exact broker symbol name, e.g. XAUUSD.")
    timeframe: Literal["M1", "M2", "M3", "M4", "M5", "M6", "M10", "M12", "M15", "M20", "M30", "H1", "H2", "H3", "H4", "H6", "H8", "H12", "D1", "W1", "MN1"]
    date_from: Optional[AwareDatetime] = Field(default=None, description="Inclusive lower bound on bar opening time. ISO 8601 with timezone or Unix seconds. YYYY-MM-DD means start of day UTC.")
    date_to: Optional[AwareDatetime] = Field(default=None, description="Inclusive upper bound on bar opening time; defaults to now. YYYY-MM-DD includes the entire day UTC.")
    count: Optional[int] = Field(default=None, ge=1, le=10000, description="Optional maximum bars, 1–10000. With both dates and no count/null, stream all available bars in the range. Otherwise defaults to 500 bars.")
    offset: int = Field(default=0, ge=0, le=100000, description="Skip this many eligible bars counting backwards from date_to (or now), regardless of output order. Use fixed date_to for stable pagination.")
    order: Literal["asc", "desc"] = Field(default="asc", description="Output order by bar opening time. Pagination always selects newest bars first, then sorts the page.")
    include_current: bool = Field(default=True, description="Include the current unfinished bar; false excludes it.")

    @field_validator("symbol")
    @classmethod
    def clean_symbol(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("symbol cannot be blank")
        return value

    @field_validator("timeframe", mode="before")
    @classmethod
    def normalize_timeframe(cls, value):
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("date_from", "date_to", mode="before")
    @classmethod
    def parse_date(cls, value, info):
        if isinstance(value, str) and len(value) == 10:
            dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt + timedelta(days=1, microseconds=-1) if info.field_name == "date_to" else dt
        return value

    @model_validator(mode="after")
    def validate_range(self):
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be earlier than or equal to date_to")
        if self.count is None and self.date_from and self.date_to and self.offset:
            raise ValueError("offset requires count for a full date range")
        return self


class CandleExportRequest(CandleRequest):
    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [
        {"symbol": "XAUUSD", "timeframe": "H1", "date_from": "2026-10-01", "date_to": "2026-10-19", "count": 500, "offset": 0, "order": "asc", "include_current": False, "format": "csv"}
    ]})
    format: Literal["csv", "json"] = Field(default="csv", description="Download format. CSV includes a header; JSON contains the same candle array as /history/candles.")


class CandleResponse(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
    real_volume: int


app = FastAPI(
    docs_url=None,
    title="MetaTrader 5 Gold Ticker API",
    version="1.3.0",
    lifespan=stream_lifespan,
    description=(
        "Read-only market data and account API backed by the connected IC Markets MT5 terminal.\n\n"
        "Click **Authorize** and enter the `API_KEY` configured in Coolify (the key only, "
        "without a Bearer prefix). Swagger sends it as the `X-API-Key` header. "
        "The root and health endpoints are public.\n\n"
        "Use the **REST API** and **WebSocket** tabs in [the documentation portal](/docs) "
        "to explore endpoints or start/stop the XAUUSD stream.\n\n"
        "Use `/symbols` to discover exact broker symbol names. Tick data may be unchanged "
        "when the market is closed. Timestamps are reported as-is by the terminal; "
        "do not assume the broker's time offset is UTC. No order-placement endpoints are exposed."
    ),
    swagger_ui_parameters={"persistAuthorization": False, "displayRequestDuration": True},
)

protected = [Depends(require_api_key)]


@app.websocket("/ws/ticks")
async def websocket_ticks(websocket: WebSocket):
    await stream_ticks(websocket, API_KEY)


@app.get("/ws/protocol", include_in_schema=False)
def websocket_protocol():
    return PROTOCOL


@app.get("/docs", response_class=HTMLResponse, include_in_schema=False)
def documentation_portal():
    return themed(HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MT5 API Documentation</title>
<style>html,body{height:100%;margin:0;font:15px system-ui;background:#101827;color:#e5edf8}body{display:flex;flex-direction:column}header{padding:16px 24px;border-bottom:1px solid #334155}h1{font-size:22px;margin:0 0 8px}p{margin:0 0 14px;color:#b8c5d9}nav{display:flex;gap:10px}button{padding:10px 20px;border:1px solid #475569;border-radius:7px;color:#e5edf8;background:#1d293b;cursor:pointer}button[aria-pressed=true]{background:#2563eb;border-color:#60a5fa}main{flex:1;min-height:0}iframe{width:100%;height:100%;border:0;background:white}iframe[hidden]{display:none}</style></head>
<body><header><h1>MetaTrader 5 API</h1><p>REST endpoints and WebSocket streaming — one documentation portal.</p>
<nav aria-label="Documentation sections"><button id="rest-tab" aria-pressed="true" aria-controls="rest">REST API</button><button id="ws-tab" aria-pressed="false" aria-controls="ws">WebSocket · XAUUSD</button></nav></header>
<main><iframe id="rest" title="REST API documentation" src="/docs/rest"></iframe><iframe id="ws" title="WebSocket documentation and tester" hidden></iframe></main>
<script>
function selectTab() {
 const active = location.hash === '#websocket' ? 'ws' : 'rest';
 for (const name of ['rest','ws']) {
  document.getElementById(name).hidden = name !== active;
  document.getElementById(name + '-tab').setAttribute('aria-pressed', String(name === active));
 }
 const ws = document.getElementById('ws');
 if (active === 'ws' && !ws.getAttribute('src')) ws.src = '/docs/websocket';
}
document.getElementById('rest-tab').onclick = () => { location.hash = 'rest'; };
document.getElementById('ws-tab').onclick = () => { location.hash = 'websocket'; };
window.addEventListener('hashchange', selectTab);selectTab();
</script></body></html>""", headers={"Cache-Control": "no-store"}))


@app.get("/docs/rest", response_class=HTMLResponse, include_in_schema=False)
def rest_documentation():
    return themed(get_swagger_ui_html(
        openapi_url=app.openapi_url, title="MT5 REST API",
        swagger_ui_parameters={"persistAuthorization": False, "displayRequestDuration": True},
    ))


@app.get("/ws/docs", include_in_schema=False)
def legacy_websocket_docs():
    return RedirectResponse("/docs#websocket", status_code=307)


@app.get("/docs/websocket", response_class=HTMLResponse, include_in_schema=False)
def websocket_docs():
    return themed(HTMLResponse("""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MT5 WebSocket Guide</title>
<style>body{box-sizing:border-box;font:16px system-ui;width:100%;max-width:1460px;margin:0 auto;padding:0 20px 32px;background:#101827;color:#e5edf8}a{color:#8bc5ff}code,pre{background:#1d293b;padding:8px;border-radius:6px}pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:400px;overflow:auto}input,button{padding:10px;margin:4px 0}input{width:280px;max-width:90%}button{cursor:pointer}</style></head>
<body><h1>MT5 WebSocket — XAUUSD</h1><p><a href="/ws/protocol" target="_blank" rel="noopener">Full protocol (JSON)</a></p>
<p>Endpoint: <code id="endpoint"></code></p>
<ul><li>Authenticate within 10 seconds. No symbols are subscribed automatically. Use Start / Stop XAUUSD.</li>
<li>Shared polling interval: <strong>1 second</strong>. Only changed ticks are sent, so a quiet or closed market may produce no new ticks.</li>
<li>Heartbeat: every 15 seconds. Broker timestamps are forwarded unchanged.</li>
<li>Reconnect with backoff and authenticate again after disconnect. No replay or guarantee of every broker tick.</li></ul>
<h2>Browser tester</h2><p>Use only on a trusted device. The key is not stored. Never embed this privileged key in a public frontend.</p>
<input id="key" type="password" autocomplete="off" placeholder="API_KEY from Coolify" aria-label="API key">
<button id="connect">Connect</button> <button id="disconnect">Disconnect</button>
<button id="start">Start XAUUSD</button> <button id="stop">Stop XAUUSD</button>
<p id="state">Disconnected</p><pre id="events" aria-live="polite"></pre>
<h2>Authentication</h2><p>Browser: send this JSON after opening the connection:</p>
<pre>{"action":"auth","api_key":"YOUR_API_KEY"}</pre>
<p>Backend clients may instead set <code>X-API-Key</code> in the handshake. Never put the key in URL query parameters.</p>
<h2>Start / stop commands</h2><p>Send subscribe to start XAUUSD, and unsubscribe to stop. When no client is subscribed, the shared reader stops polling MT5.</p>
<pre>{"action":"subscribe","symbols":["XAUUSD"]}
{"action":"unsubscribe","symbols":["XAUUSD"]}
{"action":"ping"}</pre>
<h2>Browser example</h2><pre>const ws = new WebSocket('wss://' + location.host + '/ws/ticks');
ws.onopen = () =&gt; ws.send(JSON.stringify({action: 'auth', api_key: YOUR_KEY}));
ws.onmessage = event =&gt; {
  const data = JSON.parse(event.data);
  if (data.type === 'ready') ws.send(JSON.stringify({action: 'subscribe', symbols: ['XAUUSD']}));
  if (data.type === 'tick') console.log(data.symbol, data.bid, data.ask);
};</pre>
<script>
const endpoint = 'wss://' + location.host + '/ws/ticks';
document.getElementById('endpoint').textContent = endpoint;
let socket;
const state = document.getElementById('state');
const events = document.getElementById('events');
document.getElementById('connect').onclick = () => {
  if (socket && socket.readyState < 2) return;
  const keyInput = document.getElementById('key');
  let key = keyInput.value;
  keyInput.value = '';
  if (!key) { state.textContent = 'Enter your API key first'; return; }
  events.textContent = '';
  state.textContent = 'Connecting...';
  const ws = new WebSocket(endpoint);
  socket = ws;
  ws.onopen = () => { ws.send(JSON.stringify({action:'auth', api_key:key})); key = ''; };
  ws.onmessage = event => {
    const data = JSON.parse(event.data);
    if (data.type === 'ready') state.textContent = 'Authenticated — idle. Click Start XAUUSD.';
    if (data.type === 'subscribed') state.textContent = 'Streaming: ' + data.symbols.join(', ') + ' (1s polling)';
    if (data.type === 'unsubscribed') state.textContent = 'Stopped — active symbols: ' + (data.symbols.join(', ') || 'none');
    events.textContent = (event.data + '\\n' + events.textContent).slice(0, 16000);
  };
  ws.onclose = event => { key = ''; state.textContent = 'Disconnected (' + event.code + '): ' + event.reason; };
  ws.onerror = () => { state.textContent = 'Connection error — check TLS/network'; };
};
document.getElementById('disconnect').onclick = () => { if (socket) socket.close(1000, 'Client disconnect'); };
function command(action) {
  if (!socket || socket.readyState !== WebSocket.OPEN) { state.textContent = 'Connect and authenticate first'; return; }
  socket.send(JSON.stringify({action: action, symbols: ['XAUUSD']}));
}
document.getElementById('start').onclick = () => command('subscribe');
document.getElementById('stop').onclick = () => command('unsubscribe');
</script></body></html>""", headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}))

errors = {
    403: {"model": ErrorResponse, "description": "Missing or invalid X-API-Key."},
    404: {"model": ErrorResponse, "description": "Requested symbol, account, or data not found."},
    503: {"model": ErrorResponse, "description": "MT5 bridge or broker connection unavailable."},
}


@contextmanager
def terminal(require_connection=True):
    conn = None
    try:
        conn = rpyc.classic.connect("127.0.0.1", 18812)
        conn._config["sync_request_timeout"] = 15
        mt5 = conn.modules["MetaTrader5"]
        info = mt5.terminal_info()
        if require_connection and not (info and info.connected):
            raise HTTPException(status_code=503, detail="MT5 is not connected to the broker")
        yield mt5, conn
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="MT5 bridge unavailable or request timed out")
    finally:
        if conn is not None:
            conn.close()


@app.get("/health", response_model=HealthResponse, tags=["Status"], summary="Check terminal and broker connectivity")
def health():
    try:
        with terminal(require_connection=False) as (mt5, conn):
            info = mt5.terminal_info()
            acc = mt5.account_info()
            connected = bool(info and info.connected)
            logged_in = bool(connected and acc and acc.login)
            return HealthResponse(
                status="healthy" if connected and logged_in else "unhealthy",
                mt5_connected=connected,
                build=int(info.build) if info else None,
                account_logged_in=logged_in,
            )
    except HTTPException as exc:
        return HealthResponse(status="error", mt5_connected=False, detail=exc.detail)


@app.get("/", response_model=IndexResponse, tags=["Status"], summary="API entry point")
def index():
    return {"service": "MetaTrader 5 API", "health": "/health", "docs": "/docs"}


@app.get("/symbols", response_model=list[str], dependencies=protected,
         responses=errors, tags=["Market data"], summary="List available broker symbol names")
def get_symbols():
    with terminal() as (mt5, conn):
        # Serialize in Wine rather than making thousands of remote attribute calls.
        return json.loads(str(conn.eval(
            "__import__('json').dumps([s.name for s in (__import__('MetaTrader5').symbols_get() or [])])"
        )))


@app.get("/account", response_model=AccountResponse, dependencies=protected,
         responses=errors, tags=["Account"], summary="Read the currently connected trading account")
def get_account():
    with terminal() as (mt5, conn):
        account = mt5.account_info()
        if not account or not account.login:
            raise HTTPException(status_code=404, detail="No trading account logged in")
        return dict(account._asdict())


@app.post("/history/candles", response_model=list[CandleResponse], dependencies=protected,
          responses=errors, tags=["Market data"], summary="Get recent OHLC candles",
          description="""### Mengambil history candle OHLC

**Hanya `symbol` dan `timeframe` yang wajib.** Semua filter lain boleh dihilangkan.
Klik **Authorize** dan masukkan API key, lalu **Try it out** → pilih **Full sample — semua parameter** → **Execute**.

### Contoh request lengkap
```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "date_from": "2026-10-01T00:00:00Z",
  "date_to": "2026-10-19T23:59:59Z",
  "count": 500,
  "offset": 0,
  "order": "asc",
  "include_current": false
}
```

### Parameter request body
| Parameter | Wajib? | Default jika tidak dikirim | Penjelasan |
| --- | --- | --- | --- |
| `symbol` | **Ya** | Tidak ada | Nama simbol persis dari broker, misalnya `XAUUSD`. Panjang 1–128 karakter. Lihat `GET /symbols` untuk nama yang tersedia. |
| `timeframe` | **Ya** | Tidak ada | Interval candle: `M1`, `M2`, `M3`, `M4`, `M5`, `M6`, `M10`, `M12`, `M15`, `M20`, `M30`, `H1`, `H2`, `H3`, `H4`, `H6`, `H8`, `H12`, `D1`, `W1`, `MN1`. Huruf kecil otomatis dinormalisasi. `MN1` = bulanan, `M1` = satu menit. |
| `date_from` | Tidak | Tanpa batas awal | Waktu pembukaan candle paling awal, **inklusif**. Mendukung ISO 8601 dengan timezone, Unix timestamp detik, atau `YYYY-MM-DD`. Tanggal saja berarti pukul `00:00:00 UTC`. Boleh `null`. |
| `date_to` | Tidak | Waktu sekarang | Waktu pembukaan candle paling akhir, **inklusif**. Format sama seperti `date_from`. Tanggal saja mencakup seluruh hari sampai `23:59:59.999999 UTC`. Boleh `null`. |
| `count` | Tidak | Seluruh rentang jika kedua tanggal terisi; selain itu `500` | Jika diisi: maksimal candle **per halaman**, bilangan bulat 1–10.000. Jika dihilangkan/null dan kedua tanggal terisi: seluruh candle tersedia dalam rentang. |
| `offset` | Tidak | `0` | Lewati sejumlah candle terbaru yang memenuhi filter, lalu ambil halaman berikutnya ke arah data lebih lama. Bilangan bulat 0–100.000. |
| `order` | Tidak | `"asc"` | Urutan **hasil di halaman**: `asc` = lama ke baru, `desc` = baru ke lama. Tidak mengubah arah pemilihan halaman. |
| `include_current` | Tidak | `true` | `true` menyertakan candle aktif yang belum selesai; `false` mengecualikannya. Nilai OHLC candle aktif masih dapat berubah. |

### Request minimal
```json
{"symbol": "XAUUSD", "timeframe": "M1"}
```
Mengambil maksimal 500 candle terbaru, diurutkan lama ke baru, termasuk candle aktif.

### Rentang tanggal dan timezone
- Kedua tanggal bersifat opsional dan boleh dipakai terpisah. `date_from` harus ≤ `date_to` jika keduanya dikirim.
- Contoh sehari penuh: `"date_from": "2026-10-19", "date_to": "2026-10-19"`.
- Contoh timezone Indonesia: `"2026-10-19T08:00:00+07:00"`.
- ISO datetime harus memiliki timezone (`Z` atau offset). Unix timestamp menggunakan **detik**, bukan milidetik.
- Filter membandingkan **waktu pembukaan bar**, bukan menyeleksi setiap tick di dalam candle.
- Input tanggal dikonversi ke UTC. Timestamp output dari terminal diteruskan tanpa koreksi offset broker; jangan menganggap waktu tampilan broker selalu UTC.

### Pagination
Pemilihan selalu dimulai dari candle **terbaru** sampai `date_to`, setelah filter tanggal dan `include_current` diterapkan.
Halaman pertama: `offset: 0`; berikutnya: `offset: 500` jika `count: 500`; lalu `offset: 1000`.
Tetapkan `date_to` yang sama untuk semua halaman agar data baru tidak menggeser pagination.
Jika rentang berisi lebih banyak bar daripada `count`, satu request **tidak** mengembalikan seluruh rentang.
`order: "asc"` hanya membalik urutan bar di halaman yang sudah dipilih, bukan mengambil halaman paling tua lebih dahulu.

### Respons
Array candle; setiap item memuat `time` (timestamp detik), `open`, `high`, `low`, `close`, `tick_volume`, `spread` (points broker), dan `real_volume`.
Volume riil dapat bernilai nol jika broker tidak menyediakannya. Jumlah hasil dapat lebih kecil dari `count` karena ketersediaan history dan batas **MaxBars** terminal.

### Status dan error
| HTTP | Arti |
| --- | --- |
| `200` | Berhasil. `[]` berarti tidak ada bar yang memenuhi filter pada data yang tersedia. |
| `403` | Header `X-API-Key` kosong atau salah. |
| `404` | Simbol tidak ditemukan di broker. |
| `422` | Validasi gagal: field wajib hilang, timeframe salah, tanggal tidak valid/terbalik, batas count/offset dilanggar, atau field tidak dikenal. |
| `503` | Broker/bridge tidak terhubung, timeout, atau history belum tersedia. Tunggu sinkronisasi history dan coba lagi; periksa MaxBars jika perlu. |

Endpoint ini **read-only**, tidak membuka atau mengubah posisi trading.
""")
def get_candles(payload: CandleRequest = Body(openapi_examples={
    "all_range": {"summary": "Seluruh rentang — tanpa count", "value": {
        "symbol": "XAUUSD", "timeframe": "M1", "date_from": "2026-01-01", "date_to": "2026-01-31", "include_current": False}},
    "full": {
        "summary": "Full sample — semua parameter",
        "description": "Hanya symbol dan timeframe wajib. Tanggal, count, offset, order dan include_current opsional. Ubah tanggal sesuai history yang tersedia.",
        "value": {"symbol": "XAUUSD", "timeframe": "H1", "date_from": "2026-10-01T00:00:00Z", "date_to": "2026-10-19T23:59:59Z", "count": 500, "offset": 0, "order": "asc", "include_current": False},
    },
    "minimal": {
        "summary": "Minimal — latest 500 bars",
        "description": "Only symbol and timeframe are required.",
        "value": {"symbol": "XAUUSD", "timeframe": "M1"},
    },
    "date_range": {
        "summary": "Date range — complete UTC days",
        "description": "Filter bar opening times inclusively. date_to includes the entire day.",
        "value": {"symbol": "XAUUSD", "timeframe": "H1", "date_from": "2026-10-01", "date_to": "2026-10-19", "count": 500, "offset": 0, "order": "asc", "include_current": False},
    },
    "timezone": {
        "summary": "Exact range — ISO 8601 timezone",
        "value": {"symbol": "XAUUSD", "timeframe": "M15", "date_from": "2026-10-19T08:00:00+07:00", "date_to": "2026-10-19T17:00:00+07:00", "count": 100, "include_current": False},
    },
    "pagination": {
        "summary": "Older page — fixed end time",
        "description": "Skip the newest 100 eligible bars, then return up to 100 older bars in descending order. Keep date_to fixed across pages.",
        "value": {"symbol": "XAUUSD", "timeframe": "M5", "date_to": "2026-10-19T23:59:59Z", "count": 100, "offset": 100, "order": "desc", "include_current": False},
    },
})):
    return candle_response(payload, terminal, fetch_candle_page)


def fetch_candle_page(payload):
    with terminal() as (mt5, conn):
        if not mt5.symbol_select(payload.symbol, True):
            raise HTTPException(status_code=404, detail=f"Symbol {payload.symbol} not found")
        timeframe = getattr(mt5, f"TIMEFRAME_{payload.timeframe}")
        end = int((payload.date_to or datetime.now(timezone.utc)).timestamp())
        start = payload.date_from.timestamp() if payload.date_from else None
        count = payload.count or 500
        limit = count + payload.offset + 1
        query = (
            f"__import__('MetaTrader5').copy_rates_from({payload.symbol!r}, "
            f"{int(timeframe)}, {end}, {limit})"
        )
        rows = json.loads(str(conn.eval(
            "__import__('json').dumps((lambda rates: None if rates is None else "
            "[[int(r[0]),float(r[1]),float(r[2]),float(r[3]),float(r[4]),"
            "int(r[5]),int(r[6]),int(r[7])] for r in rates])(" + query + "))"
        )))
        if rows is None:
            raise HTTPException(status_code=503, detail="MT5 history unavailable; retry after history downloads or check terminal MaxBars")
        if not payload.include_current:
            current = mt5.copy_rates_from_pos(payload.symbol, timeframe, 0, 1)
            if current is None or len(current) == 0:
                raise HTTPException(status_code=503, detail="Unable to identify current bar; retry after history downloads")
            current_time = int(current[0][0])
            rows = [row for row in rows if row[0] < current_time]
        rows = sorted((row for row in rows if (start is None or row[0] >= start) and row[0] <= end), key=lambda row: row[0], reverse=True)
        rows = rows[payload.offset:payload.offset + count]
        if payload.order == "asc":
            rows.reverse()
        return [CandleResponse(
            time=int(row[0]), open=float(row[1]), high=float(row[2]),
            low=float(row[3]), close=float(row[4]), tick_volume=int(row[5]),
            spread=int(row[6]), real_volume=int(row[7]),
        ) for row in rows]


@app.post("/history/candles/export", dependencies=protected, tags=["Market data"],
          summary="Export history candles as a CSV or JSON file", response_class=Response,
          responses={**errors, 200: {
              "description": "Download attachment. Empty results produce a CSV header only or JSON [].",
              "content": {"text/csv": {"schema": {"type": "string", "format": "binary"}},
                          "application/json": {"schema": {"type": "string", "format": "binary"}}},
              "headers": {"Content-Disposition": {"schema": {"type": "string"}, "description": "Attachment filename"}}
          }},
          description="""### Export history candle
Hanya **symbol** dan **timeframe** wajib. Semua filter dan validasi persis sama dengan
`POST /history/candles`: `date_from`, `date_to`, `count`, `offset`, `order`, `include_current`.
Lihat penjelasan lengkap parameter/rentang tanggal di endpoint tersebut.

Parameter tambahan **format** opsional: `csv` (default) atau `json`.
CSV memiliki kolom `time,open,high,low,close,tick_volume,spread,real_volume`.
`time` tetap timestamp detik dari terminal, tanpa koreksi offset broker.

**Satu ekspor = satu halaman**, maksimal 10.000 candle, default 500; bukan otomatis seluruh rentang.
Gunakan offset dan date_to tetap untuk halaman berikutnya. Pemilihan halaman dimulai dari data terbaru,
lalu hasil diurutkan sesuai order. Hasil bergantung pada history broker/MaxBars.

File dikirim sebagai attachment (Download file di Swagger), **tidak ditulis atau disimpan di disk server**.
Data kosong menghasilkan CSV dengan header saja atau JSON `[]`. Autentikasi menggunakan `X-API-Key`.

### Contoh request lengkap
```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "date_from": "2026-10-01",
  "date_to": "2026-10-19",
  "count": 500,
  "offset": 0,
  "order": "asc",
  "include_current": false,
  "format": "csv"
}
```

### Parameter request body
| Parameter | Wajib? | Default | Penjelasan |
| --- | --- | --- | --- |
| `symbol` | **Ya** | Tidak ada | Nama simbol persis dari broker, 1–128 karakter. Gunakan `GET /symbols` untuk daftar nama. |
| `timeframe` | **Ya** | Tidak ada | `M1`, `M2`, `M3`, `M4`, `M5`, `M6`, `M10`, `M12`, `M15`, `M20`, `M30`, `H1`, `H2`, `H3`, `H4`, `H6`, `H8`, `H12`, `D1`, `W1`, `MN1`. Huruf kecil dinormalisasi. `M1` satu menit; `MN1` bulanan. |
| `date_from` | Tidak | Tanpa batas awal | Batas inklusif waktu pembukaan candle. ISO 8601 dengan timezone, Unix timestamp detik, atau `YYYY-MM-DD` (awal hari UTC). Boleh null. |
| `date_to` | Tidak | Sekarang | Batas akhir inklusif. Format sama dengan date_from. Tanggal saja mencakup seluruh hari UTC. Boleh null. |
| `count` | Tidak | Seluruh rentang jika kedua tanggal terisi; selain itu `500` | Jika diisi: maksimal candle per file/halaman, 1–10.000. Jika dihilangkan/null dan kedua tanggal terisi: seluruh candle tersedia dalam rentang. |
| `offset` | Tidak | `0` | Lewati sejumlah candle terbaru yang memenuhi filter untuk mengambil halaman lebih lama. Bilangan bulat 0–100.000. |
| `order` | Tidak | `asc` | Urutan bar dalam file: lama ke baru (`asc`) atau baru ke lama (`desc`). Tidak mengubah arah pagination. |
| `include_current` | Tidak | `true` | Sertakan candle aktif yang OHLC-nya masih berubah. Gunakan false untuk mengecualikannya. |
| `format` | Tidak | `csv` | Format file: `csv` dengan header kolom, atau `json` berupa array candle. |

### Request minimal
```json
{"symbol": "XAUUSD", "timeframe": "M1"}
```
Mengunduh CSV maksimal 500 candle terbaru, lama ke baru, termasuk candle aktif.

### Rentang tanggal dan timezone
- Kedua batas tanggal opsional dan dapat digunakan terpisah. Jika keduanya dikirim, date_from harus ≤ date_to.
- Sehari penuh: `"date_from": "2026-10-19", "date_to": "2026-10-19"`.
- Jam dengan timezone Indonesia: `"2026-10-19T08:00:00+07:00"`. Datetime harus memiliki timezone (Z atau offset).
- Gunakan Unix timestamp **detik**, bukan milidetik. Filter berdasarkan **waktu pembukaan candle**, bukan waktu tiap tick.
- Input dikonversi ke UTC; timestamp terminal di output tidak dikoreksi terhadap offset broker.

### Pagination dan jumlah ekspor
Pemilihan dimulai dari candle terbaru yang memenuhi filter. Jika count=500, gunakan offset=0, lalu 500, lalu 1000.
Pertahankan date_to yang sama antarhalaman agar candle baru tidak menggeser hasil.
`order: "asc"` mengurutkan halaman terpilih, bukan memilih halaman tertua lebih dahulu.
Rentang yang panjang tidak otomatis diekspor seluruhnya; setiap request menghasilkan file untuk satu halaman.

### Kolom file dan respons
| Kolom | Arti |
| --- | --- |
| `time` | Timestamp detik waktu pembukaan candle dari terminal. |
| `open`, `high`, `low`, `close` | Harga pembukaan, tertinggi, terendah, penutupan. |
| `tick_volume` | Volume tick yang dilaporkan broker. |
| `spread` | Spread dalam points broker. |
| `real_volume` | Volume riil; dapat nol jika broker tidak menyediakannya. |

CSV menggunakan pemisah koma dan header kolom. JSON berisi array dengan field yang sama seperti endpoint non-export.
Respons memiliki `Content-Disposition: attachment` dan nama file berisi simbol, timeframe, waktu ekspor UTC, serta ekstensi.
Tidak ada file sementara atau arsip ekspor yang disimpan di SSD server.

### Cara mengunduh di Swagger
Klik **Authorize**, isi API key, buka endpoint ini, klik **Try it out**, pilih **Full sample — CSV, semua filter**,
sesuaikan nilai, lalu **Execute**. Gunakan tautan **Download file** pada respons Swagger jika ditampilkan.
Client API dapat menyimpan response body sebagai file sesuai Content-Disposition.

### Status dan error
| HTTP | Arti |
| --- | --- |
| `200` | File berhasil dibuat. Data kosong menghasilkan header CSV saja atau JSON `[]`. |
| `403` | X-API-Key kosong atau salah. |
| `404` | Simbol tidak ditemukan di broker. |
| `422` | Field wajib hilang, tanggal/timeframe/format tidak valid, rentang terbalik, count/offset melewati batas, atau field tidak dikenal. |
| `503` | Bridge/broker tidak terhubung, timeout, atau history belum tersedia. Coba lagi setelah sinkronisasi dan periksa MaxBars. |

Endpoint **read-only**, tidak membuka atau mengubah posisi trading. Ketersediaan data bergantung pada broker dan MaxBars terminal.
""")
def export_candles(payload: CandleExportRequest = Body(openapi_examples={
    "all_range": {"summary": "Seluruh rentang — tanpa count", "value": {
        "symbol": "XAUUSD", "timeframe": "M1", "date_from": "2026-01-01", "date_to": "2026-01-31", "format": "csv", "include_current": False}},
    "full_csv": {"summary": "Full sample — CSV, semua filter", "value": {
        "symbol": "XAUUSD", "timeframe": "H1", "date_from": "2026-10-01", "date_to": "2026-10-19",
        "count": 500, "offset": 0, "order": "asc", "include_current": False, "format": "csv"}},
    "minimal_csv": {"summary": "Minimal — CSV terbaru", "value": {"symbol": "XAUUSD", "timeframe": "M1"}},
    "json": {"summary": "JSON — 100 closed bars", "value": {
        "symbol": "XAUUSD", "timeframe": "M5", "count": 100, "include_current": False, "format": "json"}},
})):
    filters = CandleRequest.model_validate(payload.model_dump(exclude={"format"}))
    symbol = re.sub(r"[^A-Za-z0-9_.-]", "_", payload.symbol)
    filename = f"candles_{symbol}_{payload.timeframe}_{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.{payload.format}"
    return candle_response(filters, terminal, fetch_candle_page, export_format=payload.format, filename=filename)


RANGE_DOC = """
### Mode rentang lengkap (berlaku untuk JSON dan export)
**Dengan date_from + date_to, count dihilangkan atau null: seluruh candle yang tersedia dalam rentang dikirim.**
Tidak ada batas jumlah hasil dari API pada mode ini. Gunakan offset=0; offset bukan nol memerlukan count.
Dengan count eksplisit (1–10.000), mode pagination tetap berlaku. Tanpa rentang lengkap, default efektif 500 candle.
Data diambil per potongan waktu dan dikirim streaming tanpa file sementara atau menumpuk seluruh hasil di RAM.
Data tetap dibatasi ketersediaan history broker/MaxBars, bukan jaminan kelengkapan history.
Rentang panjang memerlukan waktu lebih lama dan dapat terkena timeout proxy/client. Jika koneksi gagal di tengah streaming,
respons terputus dan file dapat tidak lengkap; client harus memeriksa keberhasilan download, bukan hanya HTTP 200.
Pengambilan history dapat menambah cache history terminal MT5 meskipun API tidak menyimpan file ekspor.
"""
for route in app.routes:
    if getattr(route, "path", "") in ("/history/candles", "/history/candles/export"):
        route.description = RANGE_DOC + route.description.replace(
            "**Satu ekspor = satu halaman**, maksimal 10.000 candle, default 500; bukan otomatis seluruh rentang.",
            "Dengan count eksplisit, satu ekspor adalah satu halaman, maksimal 10.000 candle."
        ).replace(
            "Rentang yang panjang tidak otomatis diekspor seluruhnya; setiap request menghasilkan file untuk satu halaman.",
            "Tanpa count dengan kedua tanggal terisi, seluruh rentang diekspor."
        ).replace(
            "Jika rentang berisi lebih banyak bar daripada `count`, satu request **tidak** mengembalikan seluruh rentang.",
            "Jika count eksplisit, hasil dibatasi count; tanpa count dan dengan kedua tanggal, seluruh rentang dikirim."
        ).replace("Default count=500", "Default efektif tanpa rentang lengkap: count=500")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
