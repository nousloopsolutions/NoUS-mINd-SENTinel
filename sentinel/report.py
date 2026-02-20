"""
sentinel/report.py
Phase 7.2 — Structured report generation for legal documentation.

Input: List[ContactProfile] (aggregator), List[IntentResult] (scorer).
Output: Structured report object suitable for legal review and export.
No raw message content. No PII beyond contact identifier (phone or stable hash).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sentinel.aggregators.contact_aggregator import ContactProfile
from sentinel.models.record import IntentResult


# ── REPORT SCHEMA (no message content, no PII beyond contact id) ───────

@dataclass
class SummaryStats:
    message_count: int = 0
    call_count: int = 0
    intent_flagged_count: int = 0
    date_range_min_ms: Optional[int] = None
    date_range_max_ms: Optional[int] = None


@dataclass
class SeverityDistribution:
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0


@dataclass
class EscalationIndicator:
    contact_identifier: str   # phone or stable hash only
    trend: str                # STABLE / ESCALATING / DE-ESCALATING / UNKNOWN


@dataclass
class ContactRiskSummary:
    contact_identifier: str
    risk_score: float
    risk_label: str
    high_count: int
    medium_count: int
    low_count: int
    escalation_trend: str
    total_messages: int
    total_calls: int
    total_flags: int
    flag_rate: float


@dataclass
class Report:
    summary: SummaryStats
    severity_distribution: SeverityDistribution
    escalation_trend_indicators: List[EscalationIndicator]
    contact_risk_profiles: List[ContactRiskSummary]
    generated_at: str
    agents_md_version: str


def build_report(
    contact_profiles: List[ContactProfile],
    intent_results: List[IntentResult],
    agents_md_version: str,
) -> Report:
    """
    Build a structured report from aggregator and scorer output.
    No raw message content. Contact identifier only (phone); no names in output
    unless already part of ContactProfile.contact_name — task allows
    "contact identifier (phone number or stable hash)" so we use phone_number.
    """
    # Summary stats from profiles and intents
    message_count = sum(p.total_messages for p in contact_profiles)
    call_count = sum(p.total_calls for p in contact_profiles)
    intent_flagged_count = len(intent_results)

    all_min: List[int] = []
    all_max: List[int] = []
    for p in contact_profiles:
        if p.first_contact_ms is not None:
            all_min.append(p.first_contact_ms)
        if p.last_contact_ms is not None:
            all_max.append(p.last_contact_ms)
    for r in intent_results:
        all_min.append(r.timestamp_ms)
        all_max.append(r.timestamp_ms)
    date_min = min(all_min) if all_min else None
    date_max = max(all_max) if all_max else None

    summary = SummaryStats(
        message_count=message_count,
        call_count=call_count,
        intent_flagged_count=intent_flagged_count,
        date_range_min_ms=date_min,
        date_range_max_ms=date_max,
    )

    # Severity distribution (from intents)
    high = sum(1 for r in intent_results if (r.ai_severity or r.kw_severity or "").upper() == "HIGH")
    medium = sum(1 for r in intent_results if (r.ai_severity or r.kw_severity or "").upper() == "MEDIUM")
    low = sum(1 for r in intent_results if (r.ai_severity or r.kw_severity or "").upper() == "LOW")
    severity_distribution = SeverityDistribution(high_count=high, medium_count=medium, low_count=low)

    # Escalation indicators (from profiles)
    escalation_trend_indicators = [
        EscalationIndicator(contact_identifier=p.phone_number, trend=p.escalation_trend)
        for p in contact_profiles
    ]

    # Per-contact risk summaries (no message content)
    contact_risk_profiles = [
        ContactRiskSummary(
            contact_identifier=p.phone_number,
            risk_score=p.risk_score,
            risk_label=p.risk_label,
            high_count=p.high_count,
            medium_count=p.medium_count,
            low_count=p.low_count,
            escalation_trend=p.escalation_trend,
            total_messages=p.total_messages,
            total_calls=p.total_calls,
            total_flags=p.total_flags,
            flag_rate=p.flag_rate,
        )
        for p in contact_profiles
    ]

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return Report(
        summary=summary,
        severity_distribution=severity_distribution,
        escalation_trend_indicators=escalation_trend_indicators,
        contact_risk_profiles=contact_risk_profiles,
        generated_at=generated_at,
        agents_md_version=agents_md_version,
    )


def report_to_dict(report: Report) -> Dict:
    """Convert Report to a JSON-serializable dict (for export/signing)."""
    def _dataclass_to_dict(obj):
        if hasattr(obj, "__dataclass_fields__"):
            return {k: _dataclass_to_dict(getattr(obj, k)) for k in obj.__dataclass_fields__}
        if isinstance(obj, list):
            return [_dataclass_to_dict(x) for x in obj]
        return obj

    return _dataclass_to_dict(report)
