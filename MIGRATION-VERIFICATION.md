# Migration acceptance and GHCR publishing

## Current status: NOT certified for empty-volume deployment

The repository Dockerfile builds the Linux runtime dependencies, but does NOT
bootstrap the complete working Windows/Wine terminal environment. Publishing this
image to GHCR does NOT make it a self-contained migration image. In particular,
it does not include a prepared Wine prefix or broker terminal initialization,
Windows Python installation or an automated clean-prefix startup test.

Do not build an image by committing the running container or copying the live
Wine prefix: those may contain credentials and account/session data.

## Publish the current runtime recipe to GHCR

1. Push this workflow to GitHub. In repository Settings > Actions > General, allow
   the workflow/actions to run. The workflow requests packages:write permission.
2. Open Actions > Verify source and publish runtime recipe > Run workflow.
3. On success inspect the package ghcr.io/xhekage/mt5-docker and its image digest.
   Workflow execution/build success is not migration acceptance.
4. Keep the package private and configure package access for the repository.
5. A version tag vX.Y.Z also triggers publishing. No mutable latest tag is used.

Publishing uses GitHub Actions GITHUB_TOKEN automatically; no personal token or
registry password needs to be committed or sent through chat. The Git SSH deploy
key does not grant GHCR access.

For private-image pulls from a destination server, create a GitHub personal access
token (classic) with read:packages and access to the package, authorize organization
SSO if required, then use an interactive login:

    docker login ghcr.io -u YOUR_GITHUB_USERNAME

Paste the token at the password prompt, not as a command argument. Alternatively
configure registry credentials through Coolify. Use a credential helper where
available; the default Docker config is not encrypted secret storage.
Pin the verified image by digest in Compose, not by latest.

## Required release gates for a future self-contained image

- Pin Linux base digest, Windows Python and MT5 package versions; verify IPC patch compatibility.
- Build a CLEAN broker-terminal seed without credentials, session, account or history data.
- Application source is included at /opt/mt5-app and installed into /config on startup; fresh-image integration testing remains required.
- Initialize an empty data volume automatically without overwriting existing data.
- An in-container log maintenance worker is included; fresh-image integration testing remains required.
- On an isolated amd64 destination and new volume: test first boot, login from
  runtime secrets, health, symbols, dates, all-range history, CSV/JSON and WSS auth.
- Test invalid auth, idle/no automatic subscription, unsubscribe and restart.
- Test image update with the same volume and rollback, without exposing account data.
- Record tested image digest, date, architecture and results; only then mark the
  release migration-ready. Never use a second container with production's Wine volume.

Run service acceptance on a prepared destination (API key supplied securely via environment):

    python -m pip install 'websockets==15.0.1'
    python scripts/verify_deployment.py https://YOUR_DOMAIN

This smoke test is read-only and creates a temporary WSS subscription. Broker
history access may populate terminal caches. It is NOT proof of fresh-volume
bootstrap, every tick delivery or complete broker history. Credentials, DNS,
network connectivity and broker acceptance must be validated on each destination.

## Executable verification flow

### Gate 1: source and Docker contract (GitHub runner, not production SSD)

Run the publishing workflow. It now builds once, loads the image on the GitHub
runner, and runs `scripts/verify_image.sh` BEFORE pushing to GHCR. A failed check
prevents the publish step. The check runs with no network, no secrets, no exposed
ports, and a small tmpfs `/config`. It verifies application imports, dependency
availability, startup installation, and autostart generation with an empty mount.
It deliberately does not claim to initialize Wine or log into a broker.

The runner needs sufficient disk to build/load the multi-GB image. If hosted-runner
disk is insufficient, use a larger isolated runner; do not move builds onto the
space-constrained production server. Record the workflow URL and published digest.

### Gate 2: restored-data acceptance on the destination

Use a NEW test data directory, e.g. `/opt/mt5-verification/data`, and restore an
authorized encrypted backup of the prepared Wine environment into it. Do not copy
or mount live production data while its terminal is writing. Keep secrets outside
Git and ensure the destination has at least 25 GiB free before pulling/testing.

Supply the five credentials and the following environment values securely:

    MT5_VERIFY_IMAGE=ghcr.io/xhekage/mt5-docker@sha256:ACTUAL_DIGEST
    MT5_VERIFY_DATA=/opt/mt5-verification/data

Then on the isolated destination:

    docker compose -p mt5-verification -f compose.verify.yml config --quiet
    docker compose -p mt5-verification -f compose.verify.yml up -d
    python scripts/verify_deployment.py http://127.0.0.1:18100
    docker compose -p mt5-verification -f compose.verify.yml restart
    # Wait for healthy status, then repeat the service check.
    python scripts/verify_deployment.py http://127.0.0.1:18100

Repeat checks through the destination HTTPS proxy to cover WSS/TLS routing.
Additionally test missing/wrong API key, no automatic tick subscription, history
over 10000 bars, empty history, and log retention. Use fixed historical dates for
comparisons: live ticks, current bars, balances and history availability can change.

### Gate 3: update and rollback

Record the accepted digest and back up test data. Deploy a candidate digest on
the same isolated test data, repeat acceptance, then restore the previous digest
and test again. A rollback of code does not roll back terminal-generated data;
restore the test snapshot if needed. Do not promote until both runs pass.

### Gate 4: fresh-server-only / empty-volume bootstrap

Start with a genuinely empty dedicated directory. The current image logs a missing
prepared-terminal warning and is expected NOT to become broker-healthy. This gate
remains BLOCKED until a clean terminal/Python/MT5 bootstrap is implemented and
passes the same acceptance checks. Do not report this as a successful migration.

### Release evidence

For each accepted release record: Git commit, image digest, workflow URL, tested
host architecture, prepared-data requirements, check outputs without secrets,
restart result, update/rollback result, and destination proxy result. Acceptance
means the recorded deployment path passed, not a 100% guarantee across all hosts,
broker policies or future upstream terminal updates.
