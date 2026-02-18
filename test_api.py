"""
tests/test_api.py
─────────────────────────────────────────────────────────────────────────────
Tests for sentinel.api — SentinelAPI class (no FastAPI required).

Coverage:
  - DB existence checks
  - get_contacts: empty DB, filtering, limit/offset, JSON deserialization
  - get_contact: found / not found
  - get_messages: empty DB, filtering by phone/severity, pagination
  - get_meta: empty DB, found
  - run_scan: input validation (bad path), pipeline integration (mocked)
  - _row_to_dict: JSON field deserialization

All tests use a temporary SQLite DB — no real XML files required.
FastAPI/HTTP endpoints are NOT tested here (requires httpx + TestClient).
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sentinel.api import SentinelAPI


# ── HELPERS ──────────────────────────────────────────────────────────────────

def _make_db(tmp_path: Path) -> Path:
    """Create a minimal sentinel.db with schema populated."""
    db = tmp_path / "sentinel.db"
    conn = sqlite3.connect(str(db))
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sentinel_meta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at TEXT, run_label TEXT, schema_version TEXT,
            message_count INTEGER, call_count INTEGER,
            intent_count INTEGER, notes TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER, date_str TEXT, direction TEXT,
            contact_name TEXT, phone_number TEXT, msg_type TEXT,
            body TEXT, read INTEGER, source_file TEXT
        );
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER, date_str TEXT, call_type TEXT,
            contact_name TEXT, phone_number TEXT,
            duration_sec INTEGER, duration_fmt TEXT, source_file TEXT
        );
        CREATE TABLE IF NOT EXISTS intent_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_ts_ms INTEGER, date_str TEXT, direction TEXT,
            contact_name TEXT, phone_number TEXT, msg_type TEXT,
            body TEXT, source_file TEXT,
            kw_categories TEXT, kw_severity TEXT,
            confirmed INTEGER, ai_categories TEXT, ai_severity TEXT,
            flagged_quote TEXT, context_summary TEXT,
            context_before TEXT, context_after TEXT,
            llm_model TEXT, detection_mode TEXT
        );
        CREATE TABLE IF NOT EXISTS contact_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone_number TEXT UNIQUE, contact_name TEXT,
            total_messages INTEGER, total_calls INTEGER,
            total_flags INTEGER, flag_rate REAL,
            high_count INTEGER, medium_count INTEGER, low_count INTEGER,
            risk_score REAL, risk_label TEXT,
            category_breakdown TEXT, first_contact_ms INTEGER,
            last_contact_ms INTEGER, escalation_trend TEXT,
            relationship_tags TEXT, generated_at TEXT
        );
    """)
    conn.commit()
    conn.close()
    return db


def _insert_profile(db: Path, phone: str, name: str, risk_score: float,
                    risk_label: str, flags: int = 0) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute("""
        INSERT OR REPLACE INTO contact_profiles
        (phone_number, contact_name, total_messages, total_calls,
         total_flags, flag_rate, high_count, medium_count, low_count,
         risk_score, risk_label, category_breakdown, first_contact_ms,
         last_contact_ms, escalation_trend, relationship_tags, generated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (phone, name, 10, 2, flags, flags / 10.0, 1, 1, 1,
          risk_score, risk_label,
          json.dumps({"threats": 2}),
          1_000_000, 2_000_000, "STABLE",
          json.dumps(["ex-wife"]), "2024-01-01T00:00:00"))
    conn.commit()
    conn.close()


def _insert_intent(db: Path, phone: str, severity: str, ts: int = 100) -> None:
    conn = sqlite3.connect(str(db))
    conn.execute("""
        INSERT INTO intent_results
        (message_ts_ms, date_str, direction, contact_name, phone_number,
         msg_type, body, source_file, kw_categories, kw_severity,
         confirmed, ai_categories, ai_severity, flagged_quote,
         context_summary, context_before, context_after, llm_model, detection_mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (ts, "2024-01-01", "inbox", "Test", phone,
          "sms", "test body", "file.xml",
          json.dumps(["threats"]), severity,
          1, json.dumps(["threats"]), severity,
          "test quote", "test summary",
          json.dumps([]), json.dumps([]),
          "llama3.1:8b", "keyword"))
    conn.commit()
    conn.close()


def _insert_meta(db: Path, label: str = "test-run") -> None:
    conn = sqlite3.connect(str(db))
    conn.execute("""
        INSERT INTO sentinel_meta
        (run_at, run_label, schema_version, message_count,
         call_count, intent_count, notes)
        VALUES (?,?,?,?,?,?,?)
    """, ("2024-01-01T00:00:00", label, "2.0", 10, 5, 3,
          json.dumps({"contact_profile_count": 2})))
    conn.commit()
    conn.close()


# ── TESTS: DB EXISTENCE ───────────────────────────────────────────────────────

class TestDBExistence:
    def test_no_db_get_contacts_returns_empty(self, tmp_path):
        api = SentinelAPI(db_path=tmp_path / "nonexistent.db")
        assert api.get_contacts() == []

    def test_no_db_get_contact_returns_none(self, tmp_path):
        api = SentinelAPI(db_path=tmp_path / "nonexistent.db")
        assert api.get_contact("+16125550001") is None

    def test_no_db_get_messages_returns_empty(self, tmp_path):
        api = SentinelAPI(db_path=tmp_path / "nonexistent.db")
        assert api.get_messages() == []

    def test_no_db_get_meta_returns_none(self, tmp_path):
        api = SentinelAPI(db_path=tmp_path / "nonexistent.db")
        assert api.get_meta() is None


# ── TESTS: GET_CONTACTS ───────────────────────────────────────────────────────

class TestGetContacts:
    def test_empty_table_returns_empty_list(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        assert api.get_contacts() == []

    def test_returns_all_profiles(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Alice", 75.0, "CRITICAL")
        _insert_profile(db, "+2222", "Bob",   20.0, "MEDIUM")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts()
        assert len(results) == 2

    def test_sorted_by_risk_score_desc(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Low",  5.0,  "LOW")
        _insert_profile(db, "+2222", "High", 80.0, "CRITICAL")
        _insert_profile(db, "+3333", "Mid",  30.0, "MEDIUM")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts()
        scores = [r["risk_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_filter_by_risk_label(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Alice", 75.0, "CRITICAL")
        _insert_profile(db, "+2222", "Bob",   20.0, "MEDIUM")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts(risk_label="CRITICAL")
        assert len(results) == 1
        assert results[0]["phone_number"] == "+1111"

    def test_filter_case_insensitive_label(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Alice", 75.0, "CRITICAL")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts(risk_label="critical")
        assert len(results) == 1

    def test_limit_enforced(self, tmp_path):
        db = _make_db(tmp_path)
        for i in range(10):
            _insert_profile(db, f"+{i:010d}", f"Contact{i}", float(i), "LOW")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts(limit=3)
        assert len(results) == 3

    def test_limit_max_cap_500(self, tmp_path):
        """Requesting limit=9999 should be silently capped at 500."""
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        # Just verify no error and method accepts it
        results = api.get_contacts(limit=9999)
        assert isinstance(results, list)

    def test_offset_pagination(self, tmp_path):
        db = _make_db(tmp_path)
        for i in range(5):
            _insert_profile(db, f"+{i:010d}", f"C{i}", float(i * 10), "MEDIUM")
        api = SentinelAPI(db_path=db)
        page1 = api.get_contacts(limit=3, offset=0)
        page2 = api.get_contacts(limit=3, offset=3)
        assert len(page1) == 3
        assert len(page2) == 2
        all_phones = {r["phone_number"] for r in page1 + page2}
        assert len(all_phones) == 5  # no duplicates across pages

    def test_json_fields_deserialized(self, tmp_path):
        """category_breakdown and relationship_tags should be dicts/lists, not strings."""
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Alice", 75.0, "CRITICAL")
        api = SentinelAPI(db_path=db)
        results = api.get_contacts()
        assert isinstance(results[0]["category_breakdown"], dict)
        assert isinstance(results[0]["relationship_tags"], list)


# ── TESTS: GET_CONTACT ────────────────────────────────────────────────────────

class TestGetContact:
    def test_returns_none_for_unknown_phone(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        assert api.get_contact("+9999999999") is None

    def test_returns_profile_for_known_phone(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+16125550001", "Alice", 55.0, "HIGH")
        api = SentinelAPI(db_path=db)
        result = api.get_contact("+16125550001")
        assert result is not None
        assert result["contact_name"] == "Alice"
        assert result["risk_score"] == 55.0

    def test_phone_exact_match(self, tmp_path):
        """Partial phone should not match."""
        db = _make_db(tmp_path)
        _insert_profile(db, "+16125550001", "Alice", 55.0, "HIGH")
        api = SentinelAPI(db_path=db)
        assert api.get_contact("+1612555000") is None  # missing trailing 1

    def test_json_deserialized(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_profile(db, "+1111", "Alice", 75.0, "CRITICAL")
        api = SentinelAPI(db_path=db)
        result = api.get_contact("+1111")
        assert isinstance(result["relationship_tags"], list)


# ── TESTS: GET_MESSAGES ───────────────────────────────────────────────────────

class TestGetMessages:
    def test_empty_returns_empty_list(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        assert api.get_messages() == []

    def test_returns_all_flagged_messages(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH", ts=100)
        _insert_intent(db, "+2222", "LOW",  ts=200)
        api = SentinelAPI(db_path=db)
        results = api.get_messages()
        assert len(results) == 2

    def test_filter_by_phone(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH", ts=100)
        _insert_intent(db, "+2222", "LOW",  ts=200)
        api = SentinelAPI(db_path=db)
        results = api.get_messages(phone="+1111")
        assert len(results) == 1
        assert results[0]["phone_number"] == "+1111"

    def test_filter_by_severity(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH",   ts=100)
        _insert_intent(db, "+2222", "MEDIUM", ts=200)
        _insert_intent(db, "+3333", "LOW",    ts=300)
        api = SentinelAPI(db_path=db)
        results = api.get_messages(severity="HIGH")
        assert len(results) == 1
        assert results[0]["ai_severity"] == "HIGH"

    def test_filter_severity_case_insensitive(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH", ts=100)
        api = SentinelAPI(db_path=db)
        results = api.get_messages(severity="high")
        assert len(results) == 1

    def test_sorted_newest_first(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH", ts=100)
        _insert_intent(db, "+2222", "HIGH", ts=999)
        api = SentinelAPI(db_path=db)
        results = api.get_messages()
        assert results[0]["message_ts_ms"] > results[1]["message_ts_ms"]

    def test_limit_enforced(self, tmp_path):
        db = _make_db(tmp_path)
        for i in range(10):
            _insert_intent(db, f"+{i:010d}", "HIGH", ts=i)
        api = SentinelAPI(db_path=db)
        results = api.get_messages(limit=4)
        assert len(results) == 4

    def test_limit_max_cap_200(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        results = api.get_messages(limit=9999)
        assert isinstance(results, list)

    def test_json_fields_deserialized(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_intent(db, "+1111", "HIGH", ts=100)
        api = SentinelAPI(db_path=db)
        results = api.get_messages()
        assert isinstance(results[0]["ai_categories"], list)
        assert isinstance(results[0]["kw_categories"], list)


# ── TESTS: GET_META ───────────────────────────────────────────────────────────

class TestGetMeta:
    def test_empty_table_returns_none(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        assert api.get_meta() is None

    def test_returns_latest_run(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_meta(db, "run-one")
        _insert_meta(db, "run-two")
        api = SentinelAPI(db_path=db)
        result = api.get_meta()
        assert result is not None
        assert result["run_label"] == "run-two"

    def test_notes_deserialized(self, tmp_path):
        db = _make_db(tmp_path)
        _insert_meta(db)
        api = SentinelAPI(db_path=db)
        result = api.get_meta()
        assert isinstance(result["notes"], dict)
        assert "contact_profile_count" in result["notes"]


# ── TESTS: RUN_SCAN VALIDATION ────────────────────────────────────────────────

class TestRunScanValidation:
    def test_raises_on_nonexistent_dir(self, tmp_path):
        db = _make_db(tmp_path)
        api = SentinelAPI(db_path=db)
        with pytest.raises(ValueError, match="does not exist"):
            api.run_scan(xml_dir=tmp_path / "ghost_dir")

    def test_raises_on_file_not_dir(self, tmp_path):
        db = _make_db(tmp_path)
        file_path = tmp_path / "not_a_dir.xml"
        file_path.write_text("<xml/>")
        api = SentinelAPI(db_path=db)
        with pytest.raises(ValueError, match="not a directory"):
            api.run_scan(xml_dir=file_path)

    def test_scan_calls_pipeline_modules(self, tmp_path):
        """Integration: verify pipeline modules are called with correct args."""
        db = _make_db(tmp_path)
        xml_dir = tmp_path / "backups"
        xml_dir.mkdir()
        api = SentinelAPI(db_path=db)

        mock_msgs    = [MagicMock(phone_number="+1111")]
        mock_calls   = [MagicMock(phone_number="+1111")]
        mock_intents = [MagicMock()]
        mock_profiles = [MagicMock(risk_label="HIGH")]

        with patch("sentinel.parsers.sms_parser.parse_sms_directory",
                   return_value=mock_msgs) as p_sms, \
             patch("sentinel.parsers.call_parser.parse_call_directory",
                   return_value=mock_calls) as p_call, \
             patch("sentinel.detectors.intent_detector.run_full_analysis",
                   return_value=mock_intents) as p_intent, \
             patch("sentinel.aggregators.contact_aggregator.build_contact_profiles",
                   return_value=mock_profiles) as p_prof, \
             patch("sentinel.exporters.sqlite_exporter.export") as p_export:

            result = api.run_scan(xml_dir=xml_dir, keyword_only=True)

        p_sms.assert_called_once_with(xml_dir.resolve())
        p_call.assert_called_once_with(xml_dir.resolve())
        p_intent.assert_called_once()
        p_prof.assert_called_once()
        p_export.assert_called_once()

        assert result["status"] == "ok"
        assert result["messages_parsed"] == 1
        assert result["calls_parsed"] == 1
        assert result["intents_flagged"] == 1
        assert result["contacts_profiled"] == 1
        assert result["high_risk_contacts"] == 1

    def test_scan_address_filter_applied(self, tmp_path):
        """Surgical mode: only messages for target address passed to analysis."""
        db = _make_db(tmp_path)
        xml_dir = tmp_path / "backups"
        xml_dir.mkdir()
        api = SentinelAPI(db_path=db)

        msg_target = MagicMock(phone_number="+1111")
        msg_other  = MagicMock(phone_number="+9999")
        call_target = MagicMock(phone_number="+1111")
        call_other  = MagicMock(phone_number="+9999")

        with patch("sentinel.parsers.sms_parser.parse_sms_directory",
                   return_value=[msg_target, msg_other]), \
             patch("sentinel.parsers.call_parser.parse_call_directory",
                   return_value=[call_target, call_other]), \
             patch("sentinel.detectors.intent_detector.run_full_analysis",
                   return_value=[]) as p_intent, \
             patch("sentinel.aggregators.contact_aggregator.build_contact_profiles",
                   return_value=[]), \
             patch("sentinel.exporters.sqlite_exporter.export"):

            api.run_scan(xml_dir=xml_dir, address="+1111")

        # Only target messages/calls passed to intent detector
        call_args = p_intent.call_args
        passed_messages = call_args[0][0]
        assert all(m.phone_number == "+1111" for m in passed_messages)


# ── TESTS: _ROW_TO_DICT ───────────────────────────────────────────────────────

class TestRowToDict:
    def test_json_string_fields_deserialized(self):
        """_row_to_dict should parse JSON strings into Python objects."""
        # Simulate a sqlite3.Row by using a regular dict via DictCursor
        row = {
            "kw_categories":    '["threats","harassment"]',
            "ai_categories":    '["threats"]',
            "context_before":   '[]',
            "context_after":    '["msg1"]',
            "category_breakdown": '{"threats":3}',
            "relationship_tags":  '["ex-wife"]',
            "body": "test message",
        }

        # Wrap in something that behaves like sqlite3.Row
        class FakeRow:
            def __init__(self, d):
                self._d = d
            def keys(self):
                return self._d.keys()
            def __getitem__(self, key):
                return self._d[key]
            def __iter__(self):
                return iter(self._d.items())

        result = SentinelAPI._row_to_dict(FakeRow(row))
        assert result["category_breakdown"] == {"threats": 3}
        assert result["relationship_tags"] == ["ex-wife"]
        assert result["body"] == "test message"

    def test_none_json_fields_left_as_none(self):
        row = {
            "kw_categories": None,
            "body": "test",
        }

        class FakeRow:
            def __init__(self, d):
                self._d = d
            def keys(self):
                return self._d.keys()
            def __getitem__(self, key):
                return self._d[key]
            def __iter__(self):
                return iter(self._d.items())

        result = SentinelAPI._row_to_dict(FakeRow(row))
        assert result["kw_categories"] is None

    def test_malformed_json_left_as_is(self):
        """Malformed JSON strings should be left as-is, not raise."""
        row = {"kw_categories": "not-json{{", "body": "x"}

        class FakeRow:
            def __init__(self, d):
                self._d = d
            def keys(self):
                return self._d.keys()
            def __getitem__(self, key):
                return self._d[key]
            def __iter__(self):
                return iter(self._d.items())

        result = SentinelAPI._row_to_dict(FakeRow(row))
        assert result["kw_categories"] == "not-json{{"
