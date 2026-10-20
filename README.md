# MT5 API / WSS deployment source

Small source/configuration backup of the deployed MT5 REST and WebSocket service.
No credentials, Wine data, installer executables or Docker images are committed.

## Important: not yet a fresh-server installer

This repository preserves current code and deployment configuration, not a complete
reproducible installation from zero. The Dockerfile uses an upstream latest base
and Wine packages; these may change. Existing persistent Wine data additionally
contains IC Markets terminal, Windows Python and MetaTrader5 5.0.36 with an IPC
patch. Those binaries are NOT in Git. Preserve an encrypted backup of the working
Wine prefix or implement/test a bootstrap installer before migrating.

The IPC patch is version-specific. Do not upgrade the Windows MT5 Python package
without testing compatibility.

## Deployment on an existing prepared destination

1. Keep the working persistent data at `/opt/data/mt5-data/config`.
2. Build image explicitly: `docker build -t mt5-coolify:repaired .`.
3. Copy reviewed files from `config/` into the persistent config directory; do not
   replace or delete its `.wine` directory. Restart the MT5 service to load code.
4. Use compose.yml in Coolify, set secret environment values from .env.example,
   and configure the service HTTPS domain to internal port 8000.
5. Never run another MT5 service over the same Wine prefix concurrently.

Compose uses the locally built image. A Git push alone does not copy source into
the bind-mounted production config directory or deploy code automatically.
Do not run a second standalone Compose service beside the existing Coolify one.

For log maintenance, install systemd units from systemd/ on the host, then run
`systemctl daemon-reload` and `systemctl enable --now mt5-disk-guard.timer`.
See config/DISK-POLICY.md. This scheduler is not installed by Compose.

## API

- `/docs`: REST Swagger and WebSocket tester; shared light/dark/system theme.
- `GET /symbols`: broker symbol names, authenticated using X-API-Key.
- `POST /history/candles`: JSON candles.
- `POST /history/candles/export`: same filters, CSV/JSON attachment.
- With both dates and no count/null, history streams all available range bars.
  Otherwise default is 500 bars; explicit count supports pagination up to 10000.
- `/ws/ticks`: authenticate and explicitly subscribe; no automatic XAUUSD feed.
  Latest-tick polling every second, bounded RAM queues, no tick persistence.

## Verification after deployment

Check `/health`, authenticated symbols/history/export, WSS auth and explicit
subscribe/unsubscribe. Range results depend on broker history and MaxBars.
Long streams can time out; a broken download may be incomplete.

## Secrets and backups

Store API key, broker credentials and VNC password in Coolify, never Git.
Back up persistent data separately using encrypted external storage. Do not commit
raw Coolify database exports, rendered container inspection or terminal login INI.
Keep installation binaries and credentials out of Git history even in private repos.
