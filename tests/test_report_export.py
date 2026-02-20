"""
tests/test_report_export.py
Phase 7.3 — Export format tests.
"""

import json
import pytest
from sentinel.report import build_report, Report
from sentinel.report_export import (
    export_to_json,
    export_to_dict,
    EXPORT_FORMAT_VERSION,
)
from sentinel.aggregators.contact_aggregator import ContactProfile
from sentinel.models.record import IntentResult


def _minimal_profile() -> ContactProfile:
    return ContactProfile(
        phone_number="+16125550001",
        total_messages=5,
        total_calls=1,
        total_flags=2,
        high_count=1,
        medium_count=1,
        low_count=0,
        risk_score=15.0,
        risk_label="MEDIUM",
        first_contact_ms=1704067200000,
        last_contact_ms=1704153600000,
        escalation_trend="STABLE",
    )


def _minimal_intent() -> IntentResult:
    return IntentResult(
        record_id=1,
        timestamp_ms=1704067200000,
        date_str="2024-01-01 12:00:00",
        direction="Received",
        contact_name="",
        phone_number="+16125550001",
        msg_type="SMS",
        body="",
        source_file="sms-1.xml",
        ai_severity="HIGH",
    )


class TestReportExport:
    def test_export_includes_format_version(self):
        report = build_report([_minimal_profile()], [], agents_md_version="2026-02-20.1")
        d = export_to_dict(report)
        assert d["export_format_version"] == EXPORT_FORMAT_VERSION

    def test_export_includes_metadata(self):
        report = build_report([_minimal_profile()], [], agents_md_version="2026-02-20.1")
        d = export_to_dict(report)
        assert "report_metadata" in d
        assert d["report_metadata"]["generated_at"]
        assert d["report_metadata"]["agents_md_version"] == "2026-02-20.1"
        assert "scan_parameters" in d["report_metadata"]

    def test_export_includes_scan_parameters(self):
        report = build_report([_minimal_profile()], [], agents_md_version="2026-02-20.1")
        params = {"xml_dir": "/data", "model": "llama3.1:8b"}
        d = export_to_dict(report, scan_parameters=params)
        assert d["report_metadata"]["scan_parameters"] == params

    def test_export_includes_content_hash(self):
        report = build_report([_minimal_profile()], [], agents_md_version="2026-02-20.1")
        d = export_to_dict(report)
        assert "content_hash_sha256" in d
        assert len(d["content_hash_sha256"]) == 64
        assert all(c in "0123456789abcdef" for c in d["content_hash_sha256"])

    def test_export_json_roundtrip(self):
        report = build_report(
            [_minimal_profile()],
            [_minimal_intent()],
            agents_md_version="2026-02-20.1",
        )
        js = export_to_json(report)
        parsed = json.loads(js)
        assert parsed["export_format_version"] == EXPORT_FORMAT_VERSION
        assert "content_hash_sha256" in parsed
        assert "report" in parsed

    def test_export_no_raw_message_content(self):
        report = build_report(
            [_minimal_profile()],
            [_minimal_intent()],
            agents_md_version="2026-02-20.1",
        )
        d = export_to_dict(report)
        s = json.dumps(d)
        assert "report" in d
        assert "contact_risk_profiles" in d["report"]
        # Report schema has no message body field — scores and metadata only
        assert "body" not in s
