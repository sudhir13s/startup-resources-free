"""Derives the API key from `RESOURCEOS_PASSWORD` for the `X-ResourceOS-Key`
header check.

The raw password never crosses the network between the frontend and the API —
only the derived key does. Both sides compute
`hex HMAC-SHA256(key=password, msg="resourceos-api")`.
"""

from __future__ import annotations

import hashlib
import hmac

API_KEY_MESSAGE = b"resourceos-api"


def derive_api_key(password: str) -> str:
    """`hex HMAC-SHA256(key=password, msg="resourceos-api")` — the value both
    sides send/compare as the `X-ResourceOS-Key` header. Never the raw
    password itself."""
    return hmac.new(password.encode("utf-8"), API_KEY_MESSAGE, hashlib.sha256).hexdigest()
