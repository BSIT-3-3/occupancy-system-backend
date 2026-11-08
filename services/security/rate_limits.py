import hashlib
import os

from flask import request
from flask_limiter.util import get_remote_address


def _limit(env_key, default):
    return os.getenv(env_key, default)


# Public authentication endpoints — strict limits to blunt brute-force attempts.
AUTH_LOGIN = _limit("RATE_LIMIT_AUTH_LOGIN", "10/minute")
AUTH_REGISTER = _limit("RATE_LIMIT_AUTH_REGISTER", "5/minute")
AUTH_REFRESH = _limit("RATE_LIMIT_AUTH_REFRESH", "30/minute")

# Authenticated administrator endpoints.
READ = _limit("RATE_LIMIT_READ", "240/minute")
WRITE = _limit("RATE_LIMIT_WRITE", "60/minute")

# Device-facing endpoints. Generous so periodic monitoring and event reporting
# are never blocked.
DEVICE = _limit("RATE_LIMIT_DEVICE", "600/minute")
ASSISTANCE = _limit("RATE_LIMIT_ASSISTANCE", "120/minute")


def device_key_func():
    """Rate-limit device traffic by device credential, not by IP address.

    Room Nodes commonly report through a shared gateway, so an IP-based limit
    would let one device's traffic exhaust the budget for every other device.
    Hashing the per-device ``X-Device-Key`` gives each device its own bucket
    while still falling back to the client address for anonymous requests.
    """
    credential = request.headers.get("X-Device-Key")
    if credential:
        return "device:" + hashlib.sha256(credential.encode("utf-8")).hexdigest()
    return "addr:" + get_remote_address()
