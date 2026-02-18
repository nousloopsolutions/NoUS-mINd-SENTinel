"""
sentinel/aggregation.py
Information aggregation layer for Nous architecture.
Unified API for nous-hub, nous-vault, said-node integration.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AggregatedContact:
    """Unified contact view across messages, calls, intents, recordings."""
    phone_number: str
    contact_name: str
    total_messages: int = 0
    total_calls: int = 0
    total_recordings: int = 0
    total_flags: int = 0
    risk_score: float = 0.0
    risk_label: str = "LOW"
    relationship_tags: List[str] = field(default_factory=list)
    last_interaction_ms: Optional[int] = None
    has_transcripts: bool = False


@dataclass
class AggregatedSummary:
    """Unified summary for nous architecture consumers."""
    contacts: List[Dict[str, Any]]
    messages_count: int
    calls_count: int
    intent_flags_count: int
    recordings_count: int
    uplifts_count: int
    generated_at: str


def aggregate(db_path: Path) -> AggregatedSummary:
    """
    Aggregate all data from sentinel DB for nous-hub / nous-vault consumption.
    Single source of truth for the Nous architecture.
    """
    if not db_path.exists():
        return AggregatedSummary(
            contacts=[], messages_count=0, calls_count=0,
            intent_flags_count=0, recordings_count=0, uplifts_count=0,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Counts
    msg_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    call_count = conn.execute("SELECT COUNT(*) FROM calls").fetchone()[0]
    intent_count = conn.execute("SELECT COUNT(*) FROM intent_results").fetchone()[0]
    rec_count = 0
    try:
        rec_count = conn.execute("SELECT COUNT(*) FROM recordings").fetchone()[0]
    except sqlite3.OperationalError:
        pass

    # Contacts from contact_profiles or build from messages/calls
    contacts = []
    try:
        rows = conn.execute(
            "SELECT phone_number, contact_name, total_messages, total_calls, "
            "total_flags, risk_score, risk_label, relationship_tags "
            "FROM contact_profiles ORDER BY risk_score DESC LIMIT 200"
        ).fetchall()
        for r in rows:
            rel = r["relationship_tags"]
            if isinstance(rel, str):
                try:
                    rel = json.loads(rel) if rel else []
                except json.JSONDecodeError:
                    rel = []
            contacts.append({
                "phone_number": r["phone_number"],
                "contact_name": r["contact_name"],
                "total_messages": r["total_messages"],
                "total_calls": r["total_calls"],
                "total_flags": r["total_flags"],
                "risk_score": r["risk_score"],
                "risk_label": r["risk_label"],
                "relationship_tags": rel,
            })
    except sqlite3.OperationalError:
        pass

    # Uplifts count (approximate from high-sentiment messages)
    uplift_count = 0
    try:
        from sentinel.uplifts.extractor import extract_uplifts
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            uplifts = extract_uplifts(db_path=str(db_path), output_path=tmp, top=500)
            uplift_count = len(uplifts)
        finally:
            Path(tmp).unlink(missing_ok=True)
    except Exception:
        pass

    conn.close()
    return AggregatedSummary(
        contacts=contacts,
        messages_count=msg_count,
        calls_count=call_count,
        intent_flags_count=intent_count,
        recordings_count=rec_count,
        uplifts_count=uplift_count,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
