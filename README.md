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

Compose includes a build context for this repository and uses the locally built image.
The build does NOT install the prepared Wine prefix or copy code into `/config`.
A Git push alone does not copy source into
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

### Automated service verification

Use a separate Python environment with `websockets==15.0.1` installed.
Supply `API_KEY` through a secure environment/secret mechanism, then run:

```bash
python scripts/verify_deployment.py https://YOUR_DOMAIN
```

The script checks broker login, symbol discovery, history range handling,
JSON/CSV export parity, documentation routes, and WSS subscribe/unsubscribe.
It does not print credentials. History requests may populate terminal caches.
It verifies an already running service; it does **not** prove empty-volume bootstrap,
complete historical data availability, update/rollback safety or every-tick delivery.

## Publish an image to GitHub Container Registry (GHCR)

1. Open this repository's **Actions** tab.
2. Select **Verify source and publish runtime recipe**.
3. Choose **Run workflow**, branch `main`.
4. Wait for compilation, Docker build and registry push to finish.
5. Inspect the package **`ghcr.io/xhekage/mt5-docker`** and record its image digest.

The workflow also runs for pushed version tags matching `v*`. It publishes SHA/version
tags, not a mutable `latest`. Publishing uses the automatic GitHub Actions
`GITHUB_TOKEN` with `packages: write`; no personal registry token is committed.
Enable Actions under **Settings → Actions → General** if needed, and review package
visibility/access explicitly. Keep the package private if that is your intended policy.

**Build/publish success is not migration certification.** This workflow builds the
current runtime recipe, which still requires the prepared persistent Wine data.
It does not run the live broker smoke test or a fresh-volume integration test.

### Pulling a private image

Configure registry credentials in Coolify, or log in on the destination:

```bash
docker login ghcr.io -u YOUR_GITHUB_USERNAME
```

Enter a GitHub personal access token (classic) with `read:packages` and access to
the package at the password prompt. Never put tokens in Git, command arguments,
documentation or chat. The SSH deploy key authorizes Git, not GHCR.

After testing a release, pin its exact digest, for example:

```yaml
image: ghcr.io/xhekage/mt5-docker@sha256:REPLACE_WITH_VERIFIED_DIGEST
```

The current `compose.yml` still uses a **local build** and `pull_policy: never`.
To deploy from GHCR, replace its image reference with the verified digest, remove
the build section, and change the pull policy to `missing` (or `always` as appropriate).
Do not make that change in production until the image and prepared data are verified.

## Migration readiness

| Check | Status |
| --- | --- |
| Current prepared service: broker, REST, exports, docs, WSS smoke test | Passed on the existing server |
| GHCR workflow definition | Added; remote execution must be checked in Actions |
| Self-contained runtime with clean terminal/Wine bootstrap | Not implemented |
| Deployment with an empty data volume on another host | Not verified |
| Update/rollback on the new deployment design | Not verified |

Do not treat this repository as a guaranteed one-command fresh-server restore.
See [MIGRATION-VERIFICATION.md](MIGRATION-VERIFICATION.md) for required release gates,
registry instructions and the distinction between service checks and migration acceptance.

## Secrets and backups

Store API key, broker credentials and VNC password in Coolify, never Git.
Back up persistent data separately using encrypted external storage. Do not commit
raw Coolify database exports, rendered container inspection or terminal login INI.
Keep installation binaries and credentials out of Git history even in private repos.

## Compose matching the current Coolify service

`compose.yml` preserves the running service settings:

- image `mt5-coolify:repaired`, build from the repository Dockerfile, pull_policy never;
- restart unless-stopped, 2 CPU and 2 GiB RAM;
- CUSTOM_USER=admin and secrets supplied through environment variables;
- host mount `/opt/data/mt5-data/config:/config`;
- VNC/web desktop port `3000:3000`, API `127.0.0.1:8100:8000`;
- broker-login healthcheck and Docker log rotation 10m x 3.

Port 3000 is published on all host interfaces to match the existing Coolify setup.
Restrict it with the host firewall or bind it to localhost if remote VNC is unnecessary.
RPyC port 18812 is not published.

Old Coolify UUIDs, generated labels, container names and network IDs are omitted:
the new Coolify installation generates its own. Host systemd maintenance is separate.

### On a destination with prepared MT5 data

```bash
git clone git@github.com:xhekage/mt5-docker.git
cd mt5-docker
cp .env.example .env
chmod 600 .env
# Fill .env privately, restore the working Wine data, and copy reviewed config scripts.
docker compose -f compose.yml build
docker compose -f compose.yml up -d --no-build
curl http://127.0.0.1:8100/health
```

Do not run those commands alongside the current production MT5 container.

### Coolify from Git

Create a Git-backed Docker Compose resource, select this repository, branch main,
and Compose path `/compose.yml`. Configure the five secrets listed in .env.example,
restore the prepared persistent data on the destination, and ensure source scripts
are copied into that data directory. Set the service domain to HTTPS on internal
port 8000. Build and deploy, then verify health, REST and WSS.

This is configuration parity, NOT a fully automatic empty-server restore.
