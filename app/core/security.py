from __future__ import annotations

import hashlib
import hmac


def verify_hmac_signature(payload: bytes, secret: str, signature: str) -> bool:
    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
