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
