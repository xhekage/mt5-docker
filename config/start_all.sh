#!/bin/bash
set -eu
export WINEPREFIX=/config/.wine DISPLAY=:1 WINEDEBUG=-all
export WINEDLLOVERRIDES=mscoree=d
python3 /config/prepare_login.py
wine '/config/.wine/drive_c/Program Files/MetaTrader 5 IC Markets Global/terminal64.exe' /portable /skipupdate '/config:Z:\config\mt5-login.ini' >> /config/terminal-start.log 2>&1 &
terminal_pid=$!
wine 'C:\Python39-64\python.exe' 'Z:\config\rpyc_server_patched.py' >> /config/rpyc.log 2>&1 &
bridge_pid=$!
python3 /config/start_fastapi_bridge.py &
api_pid=$!
trap 'kill "$terminal_pid" "$bridge_pid" "$api_pid" 2>/dev/null || true' EXIT TERM INT
wait -n "$terminal_pid" "$bridge_pid" "$api_pid"
