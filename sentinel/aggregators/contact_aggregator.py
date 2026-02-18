"""
sentinel/aggregators/contact_aggregator.py
Contact-level pattern aggregation.

Aggregates per-message intent results into per-contact profiles.
Surfaces risk scores, severity breakdowns, category patterns,
and escalation trends across a contact's full communication history.

NOTE ON RISK SCORE:
  risk_score = (high*3 + medium*2 + low*1) / max(total_messages, 1) * 100
  This weighting is SPECULATIVE — calibration against labeled real-world
  data required before use in legal contexts. Label all outputs accordingly.

NOTE ON ESCALATION TREND:
  Timeline is split at median message timestamp. Flag rates compared
  between halves. Threshold: ±25% change = ESCALATING / DE-ESCALATING.
  UNKNOWN if fewer than 5 total messages.
  This is a PLAUSIBLE heuristic — not a validated clinical instrument.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sentinel.models.record import CallRecord, IntentResult, MessageRecord

logger = logging.getLogger(__name__)

# ── RISK THRESHOLDS ──────────────────────────────────────────
# SPECULATIVE: adjust after real-world calibration
RISK_THRESHOLDS = {
    'LOW':      (0.0,  15.0),
    'MEDIUM':   (15.0, 35.0),
    'HIGH':     (35.0, 60.0),
    'CRITICAL': (60.0, float('inf')),
}

SEVERITY_WEIGHTS = {'HIGH': 3, 'MEDIUM': 2, 'LOW': 1}
ESCALATION_THRESHOLD = 0.25   # 25% change between halves


# ── DATA MODEL ───────────────────────────────────────────────

@dataclass
class ContactProfile:
    """Aggregated risk and pattern profile for a single contact."""
    phone_number:       str
    contact_name:       str             = 'Unknown'

    # Volume
    total_messages:     int             = 0
    total_calls:        int             = 0
    total_flags:        int             = 0
    flag_rate:          float           = 0.0   # flags / total_messages

    # Severity counts
    high_count:         int             = 0
    medium_count:       int             = 0
    low_count:          int             = 0

    # Risk
    risk_score:         float           = 0.0   # SPECULATIVE — see module docstring
    risk_label:         str             = 'LOW'

    # Category breakdown — e.g. {'manipulation': 3, 'threat': 1}
    category_breakdown: Dict[str, int]  = field(default_factory=dict)

    # Timeline
    first_contact_ms:   Optional[int]   = None
    last_contact_ms:    Optional[int]   = None
    escalation_trend:   str             = 'UNKNOWN'  # STABLE/ESCALATING/DE-ESCALATING/UNKNOWN

    # Context
    relationship_tags:  List[str]       = field(default_factory=list)
    generated_at:       str             = ''


# ── AGGREGATION ENGINE ───────────────────────────────────────

def build_contact_profiles(
    messages:            List[MessageRecord],
    calls:               List[CallRecord],
    intents:             List[IntentResult],
    contact_relationships: Optional[Dict[str, List[str]]] = None,
) -> List[ContactProfile]:
    """
    Build one ContactProfile per unique phone number.

    Aggregates message counts, call counts, intent flags, severity
    breakdown, category patterns, escalation trend, and relationship tags.

    Args:
        messages:              All parsed message records.
        calls:                 All parsed call records.
        intents:               All intent analysis results (flagged messages only).
        contact_relationships: Optional dict mapping contact names → relationship tags.
                               Example: {'Tiffany': ['family']}

    Returns:
        List[ContactProfile], sorted descending by risk_score.
    """
    contact_relationships = contact_relationships or {}

    # ── STEP 1: index messages by phone number ────────────────
    msg_counts:   Dict[str, int]        = defaultdict(int)
    msg_names:    Dict[str, str]        = {}
    msg_timeline: Dict[str, List[int]]  = defaultdict(list)  # phone → [timestamp_ms]

    for msg in messages:
        num = msg.phone_number or 'UNKNOWN'
        msg_counts[num] += 1
        msg_names[num]   = msg.contact_name or msg_names.get(num, 'Unknown')
        msg_timeline[num].append(msg.timestamp_ms)

    # ── STEP 2: index calls by phone number ───────────────────
    call_counts: Dict[str, int] = defaultdict(int)
    for call in calls:
        num = call.phone_number or 'UNKNOWN'
        call_counts[num] += 1
        if num not in msg_names:
            msg_names[num] = call.contact_name or 'Unknown'

    # ── STEP 3: aggregate intent flags ───────────────────────
    flag_counts:      Dict[str, int]             = defaultdict(int)
    high_counts:      Dict[str, int]             = defaultdict(int)
    medium_counts:    Dict[str, int]             = defaultdict(int)
    low_counts:       Dict[str, int]             = defaultdict(int)
    category_maps:    Dict[str, Dict[str, int]]  = defaultdict(lambda: defaultdict(int))
    flag_timeline:    Dict[str, List[int]]       = defaultdict(list)  # phone → [timestamp_ms of flags]

    for intent in intents:
        num = intent.phone_number or 'UNKNOWN'
        flag_counts[num] += 1

        sev = (intent.ai_severity or intent.kw_severity or 'LOW').upper()
        if sev == 'HIGH':
            high_counts[num] += 1
        elif sev == 'MEDIUM':
            medium_counts[num] += 1
        else:
            low_counts[num] += 1

        cats = intent.ai_categories or intent.kw_categories or []
        for cat in cats:
            category_maps[num][cat] += 1

        flag_timeline[num].append(intent.timestamp_ms)

    # ── STEP 4: collect all known phone numbers ───────────────
    all_phones = set(msg_counts.keys()) | set(call_counts.keys()) | set(flag_counts.keys())

    # ── STEP 5: build profiles ────────────────────────────────
    profiles: List[ContactProfile] = []

    for num in all_phones:
        total_msgs  = msg_counts.get(num, 0)
        total_calls = call_counts.get(num, 0)
        total_flags = flag_counts.get(num, 0)
        high        = high_counts.get(num, 0)
        medium      = medium_counts.get(num, 0)
        low         = low_counts.get(num, 0)
        name        = msg_names.get(num, 'Unknown')

        # Flag rate
        flag_rate = total_flags / total_msgs if total_msgs > 0 else 0.0

        # Risk score (SPECULATIVE)
        risk_score = (
            (high * SEVERITY_WEIGHTS['HIGH'] +
             medium * SEVERITY_WEIGHTS['MEDIUM'] +
             low * SEVERITY_WEIGHTS['LOW'])
            / max(total_msgs, 1)
        ) * 100.0
        risk_score = min(risk_score, 100.0)

        # Risk label
        risk_label = _classify_risk(risk_score)

        # Category breakdown
        cat_breakdown = dict(sorted(
            category_maps[num].items(),
            key=lambda x: x[1],
            reverse=True
        ))

        # Timeline
        all_ts = msg_timeline.get(num, [])
        first_ms = min(all_ts) if all_ts else None
        last_ms  = max(all_ts) if all_ts else None

        # Escalation trend
        trend = _compute_escalation_trend(
            msg_timeline=msg_timeline.get(num, []),
            flag_timeline=flag_timeline.get(num, []),
        )

        # Relationship tags — match by name (case-insensitive)
        rel_tags = _resolve_relationship_tags(name, contact_relationships)

        profiles.append(ContactProfile(
            phone_number       = num,
            contact_name       = name,
            total_messages     = total_msgs,
            total_calls        = total_calls,
            total_flags        = total_flags,
            flag_rate          = round(flag_rate, 4),
            high_count         = high,
            medium_count       = medium,
            low_count          = low,
            risk_score         = round(risk_score, 2),
            risk_label         = risk_label,
            category_breakdown = cat_breakdown,
            first_contact_ms   = first_ms,
            last_contact_ms    = last_ms,
            escalation_trend   = trend,
            relationship_tags  = rel_tags,
            generated_at       = datetime.now(timezone.utc).isoformat(),
        ))

    # Sort descending by risk score
    profiles.sort(key=lambda p: p.risk_score, reverse=True)
    logger.info(f"Contact profiles built: {len(profiles)} contacts")
    return profiles


# ── HELPERS ──────────────────────────────────────────────────

def _classify_risk(score: float) -> str:
    for label, (lo, hi) in RISK_THRESHOLDS.items():
        if lo <= score < hi:
            return label
    return 'CRITICAL'


def _compute_escalation_trend(
    msg_timeline:  List[int],
    flag_timeline: List[int],
) -> str:
    """
    Split message history at median timestamp.
    Compare flag rate in first half vs second half.

    PLAUSIBLE heuristic — ±25% threshold is not clinically validated.
    Returns: ESCALATING / DE-ESCALATING / STABLE / UNKNOWN
    """
    if len(msg_timeline) < 5:
        return 'UNKNOWN'

    sorted_msgs = sorted(msg_timeline)
    midpoint    = sorted_msgs[len(sorted_msgs) // 2]

    first_half_msgs  = sum(1 for t in sorted_msgs if t < midpoint)
    second_half_msgs = sum(1 for t in sorted_msgs if t >= midpoint)

    first_half_flags  = sum(1 for t in flag_timeline if t < midpoint)
    second_half_flags = sum(1 for t in flag_timeline if t >= midpoint)

    rate_first  = first_half_flags  / max(first_half_msgs,  1)
    rate_second = second_half_flags / max(second_half_msgs, 1)

    if rate_first == 0 and rate_second == 0:
        return 'STABLE'

    if rate_first == 0:
        return 'ESCALATING'  # went from 0 flags to any flags

    change = (rate_second - rate_first) / rate_first

    if change > ESCALATION_THRESHOLD:
        return 'ESCALATING'
    elif change < -ESCALATION_THRESHOLD:
        return 'DE-ESCALATING'
    else:
        return 'STABLE'


def _resolve_relationship_tags(
    name: str,
    contact_relationships: Dict[str, List[str]],
) -> List[str]:
    """
    Match contact name against CONTACT_RELATIONSHIPS dict.
    Case-insensitive prefix match on first word of name.
    Returns list of tags or empty list.
    """
    if not name or not contact_relationships:
        return []

    name_lower  = name.strip().lower()
    first_token = name_lower.split()[0] if name_lower else ''

    for key, tags in contact_relationships.items():
        key_lower = key.strip().lower()
        if name_lower == key_lower or first_token == key_lower:
            return list(tags)

    return []
