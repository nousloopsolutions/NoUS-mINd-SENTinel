"""
sentinel/aggregators/contact_pattern_aggregator.py
Phase 4.2d — Contact-Level Pattern Aggregator.

Input: scored messages (IntentResult list from 4.2c scorer).
Output: per-contact aggregated risk profile.
Privacy: Aggregate patterns only. No raw message content stored or logged.
No PII in output beyond contact identifier (phone_number).
"""

from typing import Dict, List, Optional

from sentinel.aggregators.contact_aggregator import (
    ContactProfile,
    build_contact_profiles,
)
from sentinel.models.record import CallRecord, IntentResult, MessageRecord


def aggregate_from_scored_intents(
    intents: List[IntentResult],
    messages: List[MessageRecord],
    calls: List[CallRecord],
    contact_relationships: Optional[Dict[str, List[str]]] = None,
) -> List[ContactProfile]:
    """
    Build per-contact risk profiles from scorer output (4.2c).

    Input: intents from Ollama severity scorer; messages and calls for volume/timeline.
    Output: List[ContactProfile] sorted by risk_score descending.
    """
    return build_contact_profiles(
        messages=messages,
        calls=calls,
        intents=intents,
        contact_relationships=contact_relationships,
    )
