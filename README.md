# MT5 REST API & WebSocket

Read-only market data and account API for MetaTrader 5, with live WebSocket ticks,
candle history, CSV/JSON exports, and an interactive documentation portal.

## Features

- FastAPI REST endpoints with `X-API-Key` authentication.
- Broker symbol discovery and account information.
- Candle history across all 21 standard MT5 timeframes.
- Optional date range, count, offset, order, and unfinished-bar filters.
- Full available date-range streaming when both dates are supplied without count.
- CSV and JSON downloads using the same filters and history engine.
- WebSocket latest-tick polling every second, explicit subscribe/unsubscribe,
  heartbeat, bounded queues, and no tick persistence.
- English Swagger documentation and WebSocket browser tester.
- Shared light/dark/system theme with one theme picker.
- Docker healthcheck, CPU/RAM limits, and bounded log retention.
- GitHub Actions workflow for publishing the runtime image to GHCR.

## Requirements

- Linux amd64 destination with Docker Engine and Docker Compose.
- Prepared MT5 Wine data containing the broker terminal, Windows Python,
  MetaTrader5 5.0.36, and the compatible IPC patch.
- Broker credentials and outbound broker connectivity.

The Dockerfile builds the Linux runtime dependencies. The prepared Windows/Wine
environment is supplied separately through the persistent `/config` mount.

## Configuration

Copy `.env.example` to `.env`, restrict its permissions, and fill in your values:

```bash
cp .env.example .env
chmod 600 .env
```

| Variable | Description |
| --- | --- |
| `MT5_LOGIN` | Numeric trading account login. |
| `MT5_PASSWORD` | Trading account password. |
| `MT5_SERVER` | Exact broker server name. |
| `API_KEY` | Key required by protected REST and WebSocket endpoints. |
| `VNC_PASSWORD` | Password for the web desktop. |

Never commit `.env`, terminal login files, Wine account data, or registry tokens.

## Docker Compose deployment

```bash
git clone https://github.com/xhekage/mt5-docker.git
cd mt5-docker
```

Prepare the persistent directory `/opt/data/mt5-data/config` with the working Wine
environment, then copy the reviewed application files from `config/` into it.
Do not overwrite or delete its `.wine` directory. Configure `.env`, then run:

```bash
docker compose -f compose.yml build
docker compose -f compose.yml up -d --no-build
curl http://127.0.0.1:8100/health
```

The service uses 2 CPUs, 2 GiB RAM, and restart policy `unless-stopped`.
The API is bound to `127.0.0.1:8100`; web desktop port 3000 is published on host
interfaces. Restrict port 3000 with a firewall or bind it to localhost if unnecessary.
RPyC port 18812 is not published. Never run two terminals over the same Wine directory.

## Coolify deployment

1. Create a Git-backed Docker Compose resource for this repository.
2. Select branch `main` and Compose path `/compose.yml`.
3. Configure the five environment variables above.
4. Prepare the persistent data and application files on the destination host.
5. Configure your HTTPS domain for service port **8000**.
6. Build/deploy and check `/health` and `/docs`.

Coolify generates its own resource IDs, labels, container names, and networks.

## REST API

Open **`https://YOUR_DOMAIN/docs`**, choose REST API, and click **Authorize**.
Enter the API key only, without a Bearer prefix.

| Method | Route | Description |
| --- | --- | --- |
| GET | `/health` | Public terminal, broker, and login status. |
| GET | `/symbols` | Available broker symbol names. |
| GET | `/account` | Connected trading account information. |
| POST | `/history/candles` | Candle history as a JSON array. |
| POST | `/history/candles/export` | Candle history as a CSV/JSON attachment. |

### Candle history

Only `symbol` and `timeframe` are required:

```json
{"symbol": "XAUUSD", "timeframe": "M1"}
```

This returns up to 500 latest available bars. For a complete available date range:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "M1",
  "date_from": "2026-01-01",
  "date_to": "2026-01-31",
  "order": "asc",
  "include_current": false
}
```

| Filter | Behavior |
| --- | --- |
| `date_from`, `date_to` | Inclusive opening-time bounds. Accept timezone-aware ISO 8601, Unix seconds, or YYYY-MM-DD UTC day boundaries. |
| `count` | Explicit limit 1–10000. Omitted/null with both dates streams all available range bars; otherwise effective default is 500. |
| `offset` | Skip newest eligible bars, 0–100000. Nonzero offset with both dates requires count. |
| `order` | `asc` or `desc`; default `asc`. With count, sorting applies after page selection. |
| `include_current` | Include the unfinished current bar; default `true`. |

For pagination, specify count and increment offset; keep date_to fixed.
Results depend on broker history/MaxBars. Long streams can time out, and a
disconnected download may be incomplete. Terminal timestamps are not adjusted
for the broker's time offset.

### Export

Send the same filters to `/history/candles/export`, with optional `format`:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "H1",
  "count": 100,
  "include_current": false,
  "format": "csv"
}
```

Format defaults to CSV; JSON is also supported. Both contain `time`, `open`, `high`,
`low`, `close`, `tick_volume`, `spread`, and `real_volume`. Downloads are generated
without temporary files on server SSD. History retrieval can still populate the
terminal's broker-history cache.

## WebSocket

Connect to `wss://YOUR_DOMAIN/ws/ticks`. Browser clients send authentication first:

```json
{"action": "auth", "api_key": "YOUR_API_KEY"}
```

Backend clients may use the `X-API-Key` handshake header instead. Never put keys in URLs.
No symbol is subscribed automatically. After the `ready` event, send:

```json
{"action": "subscribe", "symbols": ["XAUUSD"]}
```

To stop or check responsiveness:

```json
{"action": "unsubscribe", "symbols": ["XAUUSD"]}
{"action": "ping"}
```

Ticks are polled every second and sent when changed. This is not a guarantee of
every broker tick; no replay is provided. Reconnect with backoff, authenticate,
and subscribe again. An idle/closed market may produce no new ticks.
Use the WebSocket tab in `/docs` for a browser tester, or `/ws/protocol` for protocol details.

## Logging and disk maintenance

Docker logs rotate at 10 MB × 3 files. To enable periodic MT5 file-log maintenance,
copy the units in `systemd/` to `/etc/systemd/system/`, then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mt5-disk-guard.timer
```

The guard checks every 15 minutes, bounds large `.log` files and removes expired
logs without deleting broker history. See [DISK-POLICY.md](config/DISK-POLICY.md).

## Verification

Install `websockets==15.0.1` in a separate Python environment. Supply `API_KEY`
securely through the environment, then run:

```bash
python scripts/verify_deployment.py https://YOUR_DOMAIN
```

Checks include broker login, symbols, history, CSV/JSON exports, documentation,
and WSS subscribe/unsubscribe. The script does not print the API key.

## Publish to GHCR

Open **Actions → Verify source and publish runtime recipe → Run workflow** on `main`.
The workflow builds and publishes `ghcr.io/xhekage/mt5-docker` using the automatic
GitHub Actions token. Pushing a `v*` version tag also triggers publishing.

For private pulls, configure registry credentials in Coolify or use:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Enter a token with `read:packages` and package access at the password prompt.
To use GHCR instead of local builds, remove the Compose build section, replace
the image with your tested GHCR digest, and change pull_policy from `never` to `missing`.
The published runtime still needs the prepared persistent Wine data.

## Updating

Pull the reviewed source, copy updated application files into the persistent
config directory, rebuild if runtime dependencies changed, and redeploy through
your existing deployment method. A Git push alone does not update bind-mounted code.
Keep broker credentials and encrypted data backups separate from Git.
