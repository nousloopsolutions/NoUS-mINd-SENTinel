"""
sentinel/report_signing.py
Phase 7.4 — Integrity verification for exported reports.

HMAC-SHA256 signature over export content. Key from configurable signing secret.
Verification: takes export + signature, returns bool. Fail closed: unsigned or
invalid export must not be accepted as valid.
Signing key never in logs, exceptions, or metrics.
"""

import hashlib
import hmac
from typing import Union


def _key_from_secret(secret: str) -> bytes:
    """Derive a fixed-size key from secret. Never log or expose."""
    return hashlib.sha256(secret.encode("utf-8")).digest()


def sign_export(export_content: Union[bytes, str], signing_secret: str) -> str:
    """
    Compute HMAC-SHA256 signature over export content.
    signing_secret is never logged or included in output.
    """
    key = _key_from_secret(signing_secret)
    if isinstance(export_content, str):
        export_content = export_content.encode("utf-8")
    sig = hmac.new(key, export_content, hashlib.sha256).hexdigest()
    return sig


def verify_export(
    export_content: Union[bytes, str],
    signature: str,
    signing_secret: str,
) -> bool:
    """
    Verify HMAC-SHA256 signature. Returns True only if signature is valid.
    Fail closed: returns False for unsigned, tampered, or invalid.
    """
    if not signature or not isinstance(signature, str):
        return False
    expected = sign_export(export_content, signing_secret)
    return hmac.compare_digest(expected, signature)
