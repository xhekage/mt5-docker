#!/usr/bin/env bash
# Lightweight image contract check; no broker credentials, live Wine or published ports.
set -Eeuo pipefail
image=${1:?Usage: verify_image.sh IMAGE}
docker run --rm --network none --tmpfs /config:rw,exec,size=32m \
  --entrypoint /bin/bash "$image" -Eeuc '
    trap '\''echo "Image verification failed at line $LINENO: $BASH_COMMAND" >&2'\'' ERR
    test "$(uname -m)" = x86_64
    id abc >/dev/null
    bash -n /opt/mt5-app/start_all.sh /custom-cont-init.d/90-mt5-app
    bash /custom-cont-init.d/90-mt5-app
    cmp /opt/mt5-app/start_fastapi_bridge.py /config/start_fastapi_bridge.py
    grep -Fx /config/start_all.sh /config/.config/openbox/autostart
    test -x /config/start_all.sh
    test ! -e /config/mt5-login.ini
    test ! -e /config/.wine
    PYTHONPATH=/config python3 -c "from start_fastapi_bridge import app; s=app.openapi(); assert set(s[\"components\"][\"schemas\"][\"CandleRequest\"][\"required\"]) == {\"symbol\",\"timeframe\"}; assert \"/history/candles/export\" in s[\"paths\"]"
    python3 -c "import fastapi,uvicorn,rpyc,websockets; assert websockets.__version__ == \"15.0.1\""
    echo "PASS: image imports, code installation, autostart and empty-volume contract. NOT a broker/bootstrap test."
  '
