"""Generate the private terminal configuration from Coolify environment values."""
import os
from pathlib import Path

values = {key: os.environ[key] for key in ("MT5_LOGIN", "MT5_PASSWORD", "MT5_SERVER")}
if not values["MT5_LOGIN"].isdigit():
    raise ValueError("MT5_LOGIN must be a numeric trading account ID")
if any(not value or "\n" in value or "\r" in value for value in values.values()):
    raise ValueError("MT5 credentials must be nonempty single-line values")
path = Path("/config/mt5-login.ini")
fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as config:
    config.write("[Common]\n")
    for key, name in (("MT5_LOGIN", "Login"), ("MT5_PASSWORD", "Password"), ("MT5_SERVER", "Server")):
        config.write(f"{name}={values[key]}\n")
    config.write("KeepPrivate=1\n")
path.chmod(0o600)
