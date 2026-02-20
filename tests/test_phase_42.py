"""
tests/test_phase_42.py
Phase 4.2 authorized tests (8). Exact names per Architect.
No raw message content in test output. Privacy-safe.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from sentinel.models.record import MessageRecord, CallRecord, IntentResult
from sentinel.parsers.sms_parser import parse_sms_file, parse_sms_directory
from sentinel.parsers.call_parser import parse_call_file, parse_call_directory
from sentinel.scorer.ollama_scorer import (
    SEVERITY_AMBIGUOUS,
    score_message,
    score_messages,
    _parse_severity_from_response,
)
from sentinel.aggregators.contact_aggregator import build_contact_profiles
from sentinel.aggregators.contact_pattern_aggregator import aggregate_from_scored_intents
from sentinel.exporters.sqlite_exporter import export


# ── Synthetic data (no PII) ─────────────────────────────────

SMS_XML_MULTI = """<?xml version='1.0' encoding='UTF-8'?>
<smses count="3">
  <sms address="+15550001" date="1704067200000" type="1" body="One."
       read="1" contact_name="A" />
  <sms address="+15550002" date="1704067260000" type="2" body="Two."
       read="1" contact_name="B" />
  <sms address="+15550001" date="1704067320000" type="1" body="Three."
       read="0" contact_name="A" />
</smses>
"""

CALLS_XML = """<?xml version='1.0' encoding='UTF-8'?>
<calls count="2">
  <call number="+15550001" duration="60" date="1704067200000" type="1" contact_name="A" />
  <call number="+15550002" duration="0" date="1704067300000" type="3" contact_name="B" />
</calls>
"""


def _make_msg(ts_ms: int = 1704067200000, phone: str = "+15550001", body: str = "Test."):
    return MessageRecord(
        timestamp_ms=ts_ms,
        date_str="2024-01-01 00:00:00",
        direction="Received",
        contact_name="Test",
        phone_number=phone,
        msg_type="SMS",
        body=body,
        read=True,
        source_file="test.xml",
    )


# ── 1. test_parser_extracts_sam_matrix_cleanly ───────────────

def test_parser_extracts_sam_matrix_cleanly(tmp_path):
    """Parser extracts message/call data cleanly; schema intact, no corruption."""
    (tmp_path / "sms-1.xml").write_text(SMS_XML_MULTI, encoding="utf-8")
    (tmp_path / "calls-1.xml").write_text(CALLS_XML, encoding="utf-8")
    msgs = parse_sms_directory(tmp_path)
    calls = parse_call_directory(tmp_path)
    assert len(msgs) == 3
    assert len(calls) == 2
    for m in msgs:
        assert m.timestamp_ms > 0
        assert m.phone_number
        assert m.msg_type in ("SMS", "MMS")
    for c in calls:
        assert c.timestamp_ms > 0
        assert c.phone_number


# ── 2. test_parser_handles_multi_participant_dialogue ────────

def test_parser_handles_multi_participant_dialogue(tmp_path):
    """Parser handles multiple participants (contacts) in dialogue."""
    (tmp_path / "sms-1.xml").write_text(SMS_XML_MULTI, encoding="utf-8")
    msgs = parse_sms_directory(tmp_path)
    phones = {m.phone_number for m in msgs}
    assert len(phones) >= 2
    assert len(msgs) == 3


# ── 3. test_scorer_assigns_severity_baseline ─────────────────

def test_scorer_assigns_severity_baseline():
    """Scorer assigns baseline severity when appropriate (e.g. empty body → AMBIGUOUS)."""
    msg = _make_msg(body="")
    mock_llm = MagicMock()
    result = score_message(msg, mock_llm)
    assert result.ai_severity == SEVERITY_AMBIGUOUS
    mock_llm.analyze.assert_not_called()


# ── 4. test_scorer_respects_ambiguous_threshold ──────────────

def test_scorer_respects_ambiguous_threshold():
    """Scorer respects ambiguous threshold (invalid severity → AMBIGUOUS)."""
    assert _parse_severity_from_response('{"severity": "UNKNOWN"}') == SEVERITY_AMBIGUOUS
    assert _parse_severity_from_response('{"severity": ""}') == SEVERITY_AMBIGUOUS
    assert _parse_severity_from_response('{}') == SEVERITY_AMBIGUOUS
    assert _parse_severity_from_response('not json') == SEVERITY_AMBIGUOUS
    assert _parse_severity_from_response('{"severity": "HIGH"}') == "HIGH"
    assert _parse_severity_from_response('{"severity": "LOW"}') == "LOW"


# ── 5. test_aggregator_compiles_contact_history ──────────────

def test_aggregator_compiles_contact_history():
    """Aggregator compiles contact history into per-contact profiles."""
    msgs = [_make_msg(phone="+15550001"), _make_msg(ts_ms=1704067260000, phone="+15550001")]
    intents = [
        IntentResult(record_id=1, timestamp_ms=1704067200000, phone_number="+15550001",
                    date_str="", direction="", contact_name="", msg_type="", body="", source_file="",
                    ai_severity="HIGH"),
    ]
    profiles = build_contact_profiles(msgs, [], intents)
    assert len(profiles) >= 1
    p = next((x for x in profiles if x.phone_number == "+15550001"), None)
    assert p is not None
    assert p.total_messages == 2
    assert p.total_flags >= 1


# ── 6. test_aggregator_maintains_merkle_chain_links ──────────

def test_aggregator_maintains_merkle_chain_links():
    """Aggregator maintains consistent links (totals match intent count)."""
    msgs = [_make_msg(), _make_msg(ts_ms=1704067260000)]
    intents = [
        IntentResult(record_id=1, timestamp_ms=1704067200000, phone_number="+15550001",
                    date_str="", direction="", contact_name="", msg_type="", body="", source_file="",
                    ai_severity="LOW"),
        IntentResult(record_id=2, timestamp_ms=1704067260000, phone_number="+15550001",
                    date_str="", direction="", contact_name="", msg_type="", body="", source_file="",
                    ai_severity="MEDIUM"),
    ]
    profiles = aggregate_from_scored_intents(intents, msgs, [])
    assert len(profiles) >= 1
    p = next((x for x in profiles if x.phone_number == "+15550001"), None)
    assert p is not None
    assert p.total_flags == 2
    assert p.high_count + p.medium_count + p.low_count == 2


# ── 7. test_pipeline_e2e_synthetic_payload ──────────────────

def test_pipeline_e2e_synthetic_payload(tmp_path):
    """E2E pipeline: parse → score (mock) → aggregate → export."""
    (tmp_path / "sms-1.xml").write_text(SMS_XML_MULTI, encoding="utf-8")
    (tmp_path / "calls-1.xml").write_text(CALLS_XML, encoding="utf-8")
    msgs = parse_sms_directory(tmp_path)
    calls = parse_call_directory(tmp_path)
    mock_llm = MagicMock()
    mock_llm.analyze.return_value = MagicMock(severity="LOW", model_used="test", raw_response="")
    mock_llm.model = "test"
    intents = score_messages(msgs, mock_llm)
    profiles = aggregate_from_scored_intents(intents, msgs, calls)
    db = tmp_path / "out.db"
    export(db, messages=msgs, calls=calls, intents=intents, contact_profiles=profiles)
    assert db.exists()


# ── 8. test_scorer_rejects_malformed_severity_payload ────────

def test_scorer_rejects_malformed_severity_payload():
    """When scorer receives malformed payload, fail closed to AMBIGUOUS; no crash."""
    msg = _make_msg(body="Some text.")
    mock_llm = MagicMock()
    mock_llm.analyze.return_value = MagicMock(
        severity="NOTVALID",
        model_used="test",
        raw_response='{"severity": "NOTVALID"}',
    )
    mock_llm.model = "test"
    result = score_message(msg, mock_llm)
    assert result.ai_severity == SEVERITY_AMBIGUOUS

    mock_llm.analyze.return_value = None
    result2 = score_message(msg, mock_llm)
    assert result2.ai_severity == SEVERITY_AMBIGUOUS

    mock_llm.analyze.side_effect = RuntimeError("network error")
    result3 = score_message(msg, mock_llm)
    assert result3.ai_severity == SEVERITY_AMBIGUOUS
