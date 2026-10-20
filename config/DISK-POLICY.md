# MT5 disk policy

- WSS stores no tick history on disk. Cache: latest tick per symbol (100 global),
  outbound queue: 64 messages/client, older messages dropped when full.
- Docker stdout/stderr uses json-file rotation: 10m x 3 files. This is also
  saved in Coolify raw/rendered Compose. Rotation does not bound proxy logs.
- Host systemd mt5-disk-guard.timer runs every 15 minutes. disk_guard.py only
  cleans regular .log files under this config tree, skipping symlinks.
- Logs older than 7 days are deleted; files above 10 MiB are reduced to their
  latest 5 MiB, preserving the inode. Aggregate target: 100 MiB; only logs not
  written in the last day are removed to meet it. This is NOT a hard quota:
  bursts between checks or many current files can exceed the target.
- Per-file truncation can race concurrent logging and lose log records; logs
  are diagnostic only. No terminal restart is required for maintenance.
- Logs of the guard go to host journald (host retention policy applies).
- Config over 6 GiB or host free space below 5 GiB produces a warning in the
  service journal, not a push notification or automatic history deletion.
- Broker bases/history, account configuration, Wine binaries, tester data,
  installers and repair backups are never automatically deleted.
- REST history requests may download broker history into terminal bases;
  WSS subscriptions can also cause terminal-side symbol/history synchronization.
  MaxBars is not a disk quota. No hard total MT5 disk limit is configured.
- Image builds/updates can grow Docker storage independently; do not run broad
  prune commands automatically or delete containerd files manually.

Inspect:
    systemctl list-timers mt5-disk-guard.timer
    journalctl -u mt5-disk-guard.service -n 20

Migration: copying config/Compose alone does not install the host scheduler.
Also install /etc/systemd/system/mt5-disk-guard.{service,timer}, then run:
    systemctl daemon-reload
    systemctl enable --now mt5-disk-guard.timer

The service uses /opt/data/mt5-data/config and requires host Python 3/systemd.
