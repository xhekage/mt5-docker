"""Run on a prepared destination: API_KEY=... python verify_deployment.py URL.

This checks a running service, NOT reproducibility from an empty volume.
Requires websockets>=15 for the WebSocket test. Never prints the API key.
"""
import asyncio
import csv
import io
import json
import os
import sys
import urllib.request


def main():
    base = sys.argv[1].rstrip('/')
    key = os.environ['API_KEY']

    def request(path, body=None):
        req = urllib.request.Request(base + path, headers={
            'X-API-Key': key, 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
            data=None if body is None else json.dumps(body).encode())
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.read(), response.headers

    health = json.loads(request('/health')[0])
    assert health['account_logged_in'] and health['mt5_connected']
    assert 'XAUUSD' in json.loads(request('/symbols')[0])
    seed = json.loads(request('/history/candles', {
        'symbol': 'XAUUSD', 'timeframe': 'M1', 'count': 3, 'include_current': False})[0])
    assert len(seed) == 3
    query = {'symbol': 'XAUUSD', 'timeframe': 'M1',
             'date_from': seed[0]['time'], 'date_to': seed[-1]['time'], 'include_current': False}
    assert json.loads(request('/history/candles', query)[0]) == seed
    assert json.loads(request('/history/candles/export', {**query, 'format': 'json'})[0]) == seed
    data, headers = request('/history/candles/export', {**query, 'format': 'csv'})
    assert 'attachment' in headers['Content-Disposition']
    assert len(list(csv.DictReader(io.StringIO(data.decode())))) == 3
    for path in ['/docs', '/docs/rest', '/docs/websocket']:
        assert request(path)[0]

    async def websocket_test():
        from websockets.asyncio.client import connect
        url = base.replace('https://', 'wss://', 1).replace('http://', 'ws://', 1) + '/ws/ticks'
        async with connect(url, additional_headers={'X-API-Key': key}) as ws:
            async def wait_for(kind):
                for _ in range(20):
                    event = json.loads(await asyncio.wait_for(ws.recv(), 20))
                    if event['type'] == kind:
                        return event
                raise AssertionError('Expected event not received: ' + kind)
            await wait_for('ready')
            await ws.send(json.dumps({'action': 'subscribe', 'symbols': ['XAUUSD']}))
            await wait_for('subscribed')
            await ws.send(json.dumps({'action': 'unsubscribe', 'symbols': ['XAUUSD']}))
            await wait_for('unsubscribed')
    asyncio.run(websocket_test())
    print('PASS: broker login, symbols, history, JSON/CSV exports, documentation, WSS subscribe/unsubscribe')


if __name__ == '__main__':
    main()
