"""Bound MT5 logs only. Never deletes broker history, account data or Wine files."""
import fcntl
import json
import os
import time
import sys
from pathlib import Path

ROOT = Path('/config') if Path('/config/start_all.sh').exists() else Path('/opt/data/mt5-data/config')
MAX_FILE = 10 * 1024 * 1024
MAX_LOGS = 100 * 1024 * 1024
RETENTION = 7 * 86400


def main():
    now = time.time()
    files = []
    total = 0
    changed = 0
    for folder, dirs, names in os.walk(ROOT, followlinks=False):
        dirs[:] = [d for d in dirs if not Path(folder, d).is_symlink()]
        for name in names:
            path = Path(folder, name)
            if path.is_symlink():
                continue
            try:
                stat = path.stat()
                total += stat.st_size
                # Restrict cleanup to .log files; no history databases or dumps.
                if path.suffix.lower() != '.log' or not path.is_file():
                    continue
                if now - stat.st_mtime > RETENTION:
                    path.unlink()
                    changed += 1
                    continue
                if stat.st_size > MAX_FILE:
                    # Preserve inode and permissions for processes holding append handles.
                    with path.open('r+b') as stream:
                        stream.seek(-MAX_FILE // 2, os.SEEK_END)
                        tail = stream.read()
                        stream.seek(0)
                        stream.write(tail)
                        stream.truncate()
                    changed += 1
                files.append((path.stat().st_mtime, path, path.stat().st_size))
            except FileNotFoundError:
                continue
    log_bytes = sum(s for _, _, s in files)
    for modified, path, size in sorted(files):
        if log_bytes <= MAX_LOGS:
            break
        # Do not remove today's logs: active handles must remain valid.
        if now - modified > 86400:
            try:
                path.unlink()
                log_bytes -= size
                changed += 1
            except FileNotFoundError:
                pass
    warnings = []
    if total > 6 * 1024**3:
        warnings.append('MT5 config exceeds 6 GiB; inspect history/cache; no automatic deletion')
    disk = os.statvfs(ROOT)
    if disk.f_bavail * disk.f_frsize < 5 * 1024**3:
        warnings.append('Host disk free space below 5 GiB')
    if log_bytes > MAX_LOGS:
        warnings.append('Recent logs exceed 100 MiB; retained to avoid unlinking active logs')
    print(json.dumps({'config_bytes_before_cleanup': total, 'log_bytes': log_bytes,
                      'files_changed': changed, 'warnings': warnings}))


def run_once():
    # Shared data-volume lock coordinates host and container maintenance.
    path = ROOT / '.disk-guard.lock'
    try:
        lock_file = open(path, 'a')
    except PermissionError:
        lock_file = open(path, 'r')
    with lock_file as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        main()


if __name__ == '__main__':
    while True:
        run_once()
        if '--loop' not in sys.argv:
            break
        time.sleep(900)
