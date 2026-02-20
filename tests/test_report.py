"""
tests/test_report.py
Phase 7.2 — Report generation tests.
No real message content in fixtures; structure and privacy only.
"""

import pytest
from sentinel.aggregators.contact_aggregator import ContactProfile
from sentinel.models.record import IntentResult
from sentinel.report import (
    build_report,
    report_to_dict,
    Report,
    SummaryStats,
    SeverityDistribution,
    ContactRiskSummary,
)


# Minimal fixtures: no message content in report output
def _contact_profile(
    phone_number: str = "+16125550001",
    total_messages: int = 10,
    total_calls: int = 2,
    total_flags: int = 3,
    high_count: int = 1,
    medium_count: int = 1,
    low_count: int = 1,
    risk_score: float = 20.0,
    risk_label: str = "MEDIUM",
    escalation_trend: str = "ESCALATING",
    first_contact_ms: int = 1704067200000,
    last_contact_ms: int = 1704153600000,
) -> ContactProfile:
    return ContactProfile(
        phone_number=phone_number,
        contact_name="Unknown",
        total_messages=total_messages,
        total_calls=total_calls,
        total_flags=total_flags,
        flag_rate=total_flags / max(total_messages, 1),
        high_count=high_count,
        medium_count=medium_count,
        low_count=low_count,
        risk_score=risk_score,
        risk_label=risk_label,
        first_contact_ms=first_contact_ms,
        last_contact_ms=last_contact_ms,
        escalation_trend=escalation_trend,
    )


def _intent_result(
    phone_number: str = "+16125550001",
    timestamp_ms: int = 1704067200000,
    ai_severity: str = "HIGH",
) -> IntentResult:
    return IntentResult(
        record_id=1,
        timestamp_ms=timestamp_ms,
        date_str="2024-01-01 12:00:00",
        direction="Received",
        contact_name="",
        phone_number=phone_number,
        msg_type="SMS",
        body="",  # Never used in report
        source_file="sms-1.xml",
        kw_categories=[],
        kw_severity=ai_severity,
        confirmed=True,
        ai_categories=[],
        ai_severity=ai_severity,
    )


class TestReportGeneration:
    def test_report_contains_summary_stats(self):
        profiles = [_contact_profile(total_messages=5, total_calls=1)]
        intents = [_intent_result() for _ in range(2)]
        report = build_report(profiles, intents, agents_md_version="2026-02-20.1")
        assert report.summary.message_count == 5
        assert report.summary.call_count == 1
        assert report.summary.intent_flagged_count == 2
        assert report.summary.date_range_min_ms is not None
        assert report.summary.date_range_max_ms is not None

    def test_report_includes_agents_version(self):
        report = build_report([], [], agents_md_version="2026-02-20.1")
        assert report.agents_md_version == "2026-02-20.1"

    def test_report_generated_at_iso(self):
        report = build_report([], [], agents_md_version="2026-02-20.1")
        assert "T" in report.generated_at
        assert report.generated_at.endswith("Z")

    def test_report_severity_distribution(self):
        intents = [
            _intent_result(ai_severity="HIGH"),
            _intent_result(ai_severity="HIGH"),
            _intent_result(ai_severity="MEDIUM"),
            _intent_result(ai_severity="LOW"),
        ]
        report = build_report([], intents, agents_md_version="2026-02-20.1")
        assert report.severity_distribution.high_count == 2
        assert report.severity_distribution.medium_count == 1
        assert report.severity_distribution.low_count == 1

    def test_report_contact_risk_profiles_no_message_content(self):
        profiles = [_contact_profile(phone_number="+15551234567")]
        report = build_report(profiles, [], agents_md_version="2026-02-20.1")
        assert len(report.contact_risk_profiles) == 1
        cp = report.contact_risk_profiles[0]
        assert cp.contact_identifier == "+15551234567"
        assert hasattr(cp, "risk_score") and hasattr(cp, "risk_label")
        assert not hasattr(cp, "body")
        # Report schema has no body field anywhere
        d = report_to_dict(report)
        assert "body" not in str(d)

    def test_report_escalation_indicators(self):
        profiles = [
            _contact_profile(phone_number="+1", escalation_trend="ESCALATING"),
            _contact_profile(phone_number="+2", escalation_trend="STABLE"),
        ]
        report = build_report(profiles, [], agents_md_version="2026-02-20.1")
        assert len(report.escalation_trend_indicators) == 2
        trends = {e.contact_identifier: e.trend for e in report.escalation_trend_indicators}
        assert trends["+1"] == "ESCALATING"
        assert trends["+2"] == "STABLE"

    def test_report_to_dict_serializable(self):
        import json
        report = build_report(
            [_contact_profile()],
            [_intent_result()],
            agents_md_version="2026-02-20.1",
        )
        d = report_to_dict(report)
        json_str = json.dumps(d)
        assert "agents_md_version" in json_str
        assert "2026-02-20.1" in json_str
        assert "summary" in d
        assert "contact_risk_profiles" in d
