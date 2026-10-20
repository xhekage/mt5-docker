"""Shared English endpoint documentation."""
HISTORY_DOCS = '''
## Candle history filters
Only **symbol** and **timeframe** are required. Click **Authorize**, enter your API key,
then **Try it out** and select an example.

### Complete request example
```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "date_from": "2026-01-01",
  "date_to": "2026-01-31",
  "count": null,
  "offset": 0,
  "order": "asc",
  "include_current": false
}
```

### Request parameters
| Parameter | Required | Default | Description |
| --- | --- | --- | --- |
| symbol | **Yes** | None | Exact broker symbol, 1–128 characters. Discover names with GET /symbols. |
| timeframe | **Yes** | None | M1, M2, M3, M4, M5, M6, M10, M12, M15, M20, M30, H1, H2, H3, H4, H6, H8, H12, D1, W1, MN1. Case is normalized. M1 means one minute; MN1 means one month. |
| date_from | No | No lower bound | Inclusive bar-opening time. ISO 8601 with timezone, Unix seconds, or YYYY-MM-DD (start of UTC day). Null is allowed. |
| date_to | No | Now | Inclusive upper bound. Same formats. A date without time includes the entire UTC day. Null is allowed. |
| count | No | All available range bars if both dates are set; otherwise 500 | Explicit count: integer 1–10000. Omitted/null count with both dates streams the complete available range. |
| offset | No | 0 | Skip newest eligible bars, integer 0–100000. A nonzero offset with both dates requires explicit count. |
| order | No | asc | asc: oldest to newest; desc: newest to oldest. With explicit count, sorting applies after selecting the page. |
| include_current | No | true | Include the unfinished current bar. Use false for closed bars only. |

### Minimal request
```json
{"symbol": "XAUUSD", "timeframe": "M1"}
```
Returns up to 500 latest bars, oldest first, including the current bar.

### Dates and timezones
Both dates are optional and may be supplied independently. When both are supplied,
date_from must not exceed date_to. A single full day uses the same YYYY-MM-DD for
both dates. Exact datetimes require Z or an offset, for example 2026-01-19T08:00:00+07:00.
Numeric timestamps use seconds. Filters apply to opening time, not individual ticks.
Inputs are converted to UTC; terminal timestamps are forwarded without broker-offset correction.

### Complete range and pagination
With both dates and omitted/null count, all available range bars are streamed in
bounded time chunks, without temporary export files or buffering the full range in RAM.
With explicit count, select newest eligible bars first: offset 0, 500, 1000 for count 500.
Keep date_to fixed between pages. Ascending order does not select the oldest page first.
Results depend on broker history and terminal MaxBars; completeness is not guaranteed.
History retrieval may grow the terminal history cache even though exports are not saved.
Long requests may hit client/proxy timeouts. A failure after streaming starts aborts
the response; HTTP 200 alone does not prove a complete download.

### Response fields
| Field | Meaning |
| --- | --- |
| time | Bar opening timestamp, seconds as reported by the terminal. |
| open, high, low, close | Opening, highest, lowest and closing prices. |
| tick_volume | Broker-reported tick volume. |
| spread | Spread in broker points. |
| real_volume | Real volume; may be zero when unavailable. |

### Status codes
| HTTP | Meaning |
| --- | --- |
| 200 | Success. No matching available bars yields an empty result. |
| 403 | Missing or invalid X-API-Key. |
| 404 | Broker symbol not found. |
| 422 | Missing required fields, invalid dates/timeframe/count/offset, reversed range, or unknown fields. |
| 503 | Bridge/broker unavailable, timeout, or unavailable history. Retry after synchronization and check MaxBars. |

Read-only: this endpoint never opens or modifies trading positions.
'''

EXPORT_DOCS = '''
## File download
Uses exactly the same history engine, filters and validation as POST /history/candles.
Additional optional parameter **format**: **csv** (default) or **json**.
Add `"format": "csv"` to the complete example below to download CSV.

CSV uses comma-separated fields and a header. JSON uses the same array as the normal endpoint.
Empty data produces a CSV header only or JSON []. Responses have Content-Disposition: attachment
with a sanitized symbol, timeframe, UTC generation time and file extension.
Files are streamed directly and never saved to server SSD. In Swagger, click Execute,
then Download file if shown. API clients should save the response body using the attachment filename.
''' + HISTORY_DOCS
