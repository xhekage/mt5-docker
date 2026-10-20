"""Shared bounded-memory JSON/CSV serialization and range retrieval."""
import csv
import io
import json
import math
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

FIELDS = ('time', 'open', 'high', 'low', 'close', 'tick_volume', 'spread', 'real_volume')


def range_rows(payload, terminal):
    low = math.ceil(payload.date_from.timestamp())
    high = math.floor(payload.date_to.timestamp())
    with terminal() as (mt5, conn):
        if not mt5.symbol_select(payload.symbol, True):
            raise HTTPException(404, 'Symbol not found')
        timeframe = int(getattr(mt5, 'TIMEFRAME_' + payload.timeframe))
        if not payload.include_current:
            current = mt5.copy_rates_from_pos(payload.symbol, timeframe, 0, 1)
            if current is None or len(current) == 0:
                raise HTTPException(503, 'Unable to identify current bar')
            high = min(high, int(current[0][0]) - 1)
    # At most one UTC day per remote call (<=1440 M1 bars).
    while low <= high:
        if payload.order == 'asc':
            start, end = low, min(low + 86399, high)
            low = end + 1
        else:
            start, end = max(low, high - 86399), high
            high = start - 1
        with terminal() as (mt5, conn):
            query = f"__import__('MetaTrader5').copy_rates_range({payload.symbol!r}, {timeframe}, {start}, {end})"
            rows = json.loads(str(conn.eval(
                "__import__('json').dumps((lambda r: None if r is None else "
                "[[int(x[0]),float(x[1]),float(x[2]),float(x[3]),float(x[4]),int(x[5]),int(x[6]),int(x[7])] for x in r])(" + query + "))"
            )))
        if rows is None:
            raise HTTPException(503, 'MT5 history unavailable; range export stopped')
        for row in sorted(rows, key=lambda x: x[0], reverse=payload.order == 'desc'):
            if start <= row[0] <= end:
                yield dict(zip(FIELDS, row))


def encode(rows, fmt):
    if fmt == 'csv':
        output = io.StringIO(newline='')
        writer = csv.DictWriter(output, fieldnames=FIELDS)
        writer.writeheader()
        yield output.getvalue()
        for row in rows:
            output.seek(0)
            output.truncate()
            writer.writerow(row)
            yield output.getvalue()
    else:
        yield '['
        separator = ''
        for row in rows:
            yield separator + json.dumps(row, allow_nan=False)
            separator = ','
        yield ']'


def candle_response(payload, terminal, fetch_page, export_format=None, filename=None):
    full_range = payload.count is None and payload.date_from is not None and payload.date_to is not None
    rows = range_rows(payload, terminal) if full_range else (r.model_dump() for r in fetch_page(payload))
    # Fetch first bar before starting the HTTP response so initial bridge errors
    # retain their proper HTTP status. Later failures abort, never fake success.
    first = next(rows, None)

    def values():
        try:
            if first is not None:
                yield first
            yield from rows
        finally:
            rows.close()

    headers = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}
    if filename:
        headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return StreamingResponse(encode(values(), export_format or 'json'), headers=headers,
                             media_type='text/csv' if export_format == 'csv' else 'application/json')
