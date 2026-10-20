#!/usr/bin/env bash
set -euo pipefail
# LinuxServer custom-init runs as root, before the desktop session starts.
# Application source is versioned in the image; never replace persistent Wine data.
mkdir -p /config/.config/openbox
for source in /opt/mt5-app/*.py /opt/mt5-app/*.sh /opt/mt5-app/*.md; do
    [[ -f "$source" ]] || continue
    install -m 0644 -o abc -g abc "$source" "/config/$(basename "$source")"
done
chmod 0755 /config/start_all.sh
printf '%s\n' '/config/start_all.sh' > /config/.config/openbox/autostart
chown abc:abc /config/.config/openbox/autostart
terminal='/config/.wine/drive_c/Program Files/MetaTrader 5 IC Markets Global/terminal64.exe'
if [[ ! -f "$terminal" ]]; then
    echo '[mt5-init] Prepared IC Markets Wine data is missing. Restore it before starting MT5.' >&2
    echo '[mt5-init] This image does not bootstrap a fresh Windows terminal environment.' >&2
fi
