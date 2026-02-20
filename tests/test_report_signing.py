"""
tests/test_report_signing.py
Phase 7.4 — Signed output tests.
"""

import logging
import pytest
from sentinel.report_signing import sign_export, verify_export


SECRET = "test-signing-secret-never-log"
EXPORT_BODY = b'{"export_format_version":"1.0","report":{}}'


class TestSignedExport:
    def test_signed_export_verifies(self):
        sig = sign_export(EXPORT_BODY, SECRET)
        assert verify_export(EXPORT_BODY, sig, SECRET) is True

    def test_tampered_export_fails_verification(self):
        sig = sign_export(EXPORT_BODY, SECRET)
        tampered = b'{"export_format_version":"1.0","report":{"tampered":true}}'
        assert verify_export(tampered, sig, SECRET) is False

    def test_unsigned_export_rejected(self):
        assert verify_export(EXPORT_BODY, "", SECRET) is False
        assert verify_export(EXPORT_BODY, "0" * 64, SECRET) is False
        assert verify_export(EXPORT_BODY, "not-a-hex-signature", SECRET) is False

    def test_signing_key_never_logged(self):
        # Ensure sign_export/verify_export do not log the secret
        log_capture: list = []
        handler = logging.Handler()
        handler.emit = lambda r: log_capture.append(r.getMessage())
        logger = logging.getLogger("sentinel.report_signing")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        try:
            sign_export(EXPORT_BODY, SECRET)
            verify_export(EXPORT_BODY, sign_export(EXPORT_BODY, SECRET), SECRET)
            for msg in log_capture:
                assert SECRET not in msg
        finally:
            logger.removeHandler(handler)

    def test_different_secret_different_signature(self):
        sig1 = sign_export(EXPORT_BODY, "secret1")
        sig2 = sign_export(EXPORT_BODY, "secret2")
        assert sig1 != sig2
        assert verify_export(EXPORT_BODY, sig1, "secret2") is False
        assert verify_export(EXPORT_BODY, sig2, "secret1") is False

    def test_str_content_supported(self):
        content = '{"version":"1.0"}'
        sig = sign_export(content, SECRET)
        assert verify_export(content, sig, SECRET) is True
        assert verify_export(content + "x", sig, SECRET) is False
