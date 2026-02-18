"""
tests/test_parsers.py
Unit tests for parsers and detectors.
Generates synthetic XML test data — no real messages needed.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from sentinel.parsers.sms_parser      import parse_sms_file, parse_sms_directory
from sentinel.parsers.call_parser     import parse_call_file
from sentinel.detectors.keyword_detector import scan_messages
from sentinel.exporters.sqlite_exporter  import export


# ── FIXTURE: Synthetic SMS XML ────────────────────────────────

SAMPLE_SMS_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<smses count="4">
  <sms protocol="0" address="+16125550001" date="1704067200000"
       type="1" subject="null" body="You are worthless and stupid."
       toa="null" sc_toa="null" service_center="null" read="1"
       status="-1" locked="0" readable_date="Jan 1, 2024 12:00:00 AM"
       contact_name="Test Contact" />
  <sms protocol="0" address="+16125550001" date="1704067260000"
       type="2" subject="null" body="I appreciate you reaching out."
       toa="null" sc_toa="null" service_center="null" read="1"
       status="-1" locked="0" readable_date="Jan 1, 2024 12:01:00 AM"
       contact_name="Test Contact" />
  <sms protocol="0" address="+16125550002" date="1704067320000"
       type="1" subject="null" body="You will regret this. I will take the kids."
       toa="null" sc_toa="null" service_center="null" read="0"
       status="-1" locked="0" readable_date="Jan 1, 2024 12:02:00 AM"
       contact_name="Other Contact" />
  <sms protocol="0" address="+16125550002" date="1704067380000"
       type="1" subject="null" body="Completely benign message about the weather."
       toa="null" sc_toa="null" service_center="null" read="0"
       status="-1" locked="0" readable_date="Jan 1, 2024 12:03:00 AM"
       contact_name="Other Contact" />
  <mms date="1704067440000" address="+16125550001" msg_box="1" read="1"
       contact_name="Test Contact" m_id="mid1" m_type="132">
    <parts>
      <part seq="0" ct="text/plain" name="null" chset="null" cd="null"
            fn="null" cid="null" cl="null" ctt_s="null" ctt_t="null"
            text="After everything I did for you, you only think of yourself." />
    </parts>
  </mms>
</smses>
"""

SAMPLE_CALLS_XML = """<?xml version='1.0' encoding='UTF-8' standalone='yes' ?>
<calls count="3">
  <call number="+16125550001" duration="120" date="1704067200000"
        type="1" readable_date="Jan 1, 2024 12:00:00 AM"
        contact_name="Test Contact" />
  <call number="+16125550002" duration="0" date="1704067500000"
        type="3" readable_date="Jan 1, 2024 12:05:00 AM"
        contact_name="Other Contact" />
  <call number="+16125550001" duration="300" date="1704067800000"
        type="2" readable_date="Jan 1, 2024 12:10:00 AM"
        contact_name="Test Contact" />
</calls>
"""


@pytest.fixture
def tmp_xml_dir(tmp_path):
    (tmp_path / 'sms-2024-01-01.xml').write_text(SAMPLE_SMS_XML, encoding='utf-8')
    (tmp_path / 'calls-2024-01-01.xml').write_text(SAMPLE_CALLS_XML, encoding='utf-8')
    return tmp_path


# ── SMS PARSER TESTS ─────────────────────────────────────────

class TestSmsParser:

    def test_parse_sms_file_returns_records(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'sms-2024-01-01.xml'
        records = parse_sms_file(path)
        assert len(records) == 5   # 4 SMS + 1 MMS

    def test_sms_direction_mapping(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'sms-2024-01-01.xml'
        records = parse_sms_file(path)
        sms     = [r for r in records if r.msg_type == 'SMS']
        received = [r for r in sms if r.direction == 'Received']
        sent     = [r for r in sms if r.direction == 'Sent']
        assert len(received) == 3
        assert len(sent)     == 1

    def test_mms_body_extracted(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'sms-2024-01-01.xml'
        records = parse_sms_file(path)
        mms     = [r for r in records if r.msg_type == 'MMS']
        assert len(mms) == 1
        assert 'everything I did' in mms[0].body

    def test_phone_sanitization(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'sms-2024-01-01.xml'
        records = parse_sms_file(path)
        for r in records:
            assert all(c.isdigit() or c in '+-() ' for c in r.phone_number)

    def test_deduplication_in_directory(self, tmp_xml_dir):
        # Write same file twice under different names
        content = (tmp_xml_dir / 'sms-2024-01-01.xml').read_text()
        (tmp_xml_dir / 'sms-2024-01-02.xml').write_text(content, encoding='utf-8')
        records = parse_sms_directory(tmp_xml_dir)
        # Should still be 5, not 10
        assert len(records) == 5

    def test_malformed_xml_returns_empty(self, tmp_path):
        bad = tmp_path / 'sms-bad.xml'
        bad.write_text('<smses><sms BROKEN', encoding='utf-8')
        records = parse_sms_file(bad)
        assert records == []


# ── CALL PARSER TESTS ────────────────────────────────────────

class TestCallParser:

    def test_parse_calls(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'calls-2024-01-01.xml'
        records = parse_call_file(path)
        assert len(records) == 3

    def test_call_type_labels(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'calls-2024-01-01.xml'
        records = parse_call_file(path)
        types   = {r.call_type for r in records}
        assert 'Incoming'  in types
        assert 'Outgoing'  in types
        assert 'Missed'    in types

    def test_duration_format(self, tmp_xml_dir):
        path    = tmp_xml_dir / 'calls-2024-01-01.xml'
        records = parse_call_file(path)
        long_call = next(r for r in records if r.duration_sec == 300)
        assert '5m' in long_call.duration_fmt


# ── KEYWORD DETECTOR TESTS ───────────────────────────────────

class TestKeywordDetector:

    def test_detects_insult(self, tmp_xml_dir):
        from sentinel.parsers.sms_parser import parse_sms_directory
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages)
        insult_flags = [r for r in results if 'INSULT' in r.kw_categories]
        assert len(insult_flags) >= 1

    def test_detects_threat(self, tmp_xml_dir):
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages)
        threat_flags = [r for r in results if 'THREAT' in r.kw_categories]
        assert len(threat_flags) >= 1

    def test_detects_custody(self, tmp_xml_dir):
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages)
        custody_flags = [r for r in results if 'CUSTODY' in r.kw_categories]
        assert len(custody_flags) >= 1

    def test_benign_message_not_flagged(self, tmp_xml_dir):
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages)
        flagged_bodies = {r.body for r in results}
        assert 'Completely benign message about the weather.' not in flagged_bodies

    def test_context_window_populated(self, tmp_xml_dir):
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages, context_window=2)
        # At least one result should have context
        has_context = any(
            len(r.context_before) > 0 or len(r.context_after) > 0
            for r in results
        )
        assert has_context

    def test_severity_threat_is_high(self, tmp_xml_dir):
        messages = parse_sms_directory(tmp_xml_dir)
        results  = scan_messages(messages)
        for r in results:
            if 'THREAT' in r.kw_categories:
                assert r.kw_severity == 'HIGH'


# ── SQLITE EXPORTER TESTS ────────────────────────────────────

class TestSQLiteExporter:

    def test_export_creates_db(self, tmp_xml_dir, tmp_path):
        from sentinel.parsers.sms_parser  import parse_sms_directory
        from sentinel.parsers.call_parser import parse_call_directory
        messages = parse_sms_directory(tmp_xml_dir)
        calls    = parse_call_directory(tmp_xml_dir)
        db_path  = tmp_path / 'test.db'
        export(db_path, messages=messages, calls=calls)
        assert db_path.exists()

    def test_messages_queryable(self, tmp_xml_dir, tmp_path):
        import sqlite3
        from sentinel.parsers.sms_parser import parse_sms_directory
        messages = parse_sms_directory(tmp_xml_dir)
        db_path  = tmp_path / 'test.db'
        export(db_path, messages=messages)
        conn     = sqlite3.connect(str(db_path))
        count    = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        conn.close()
        assert count == 5

    def test_dedup_on_reimport(self, tmp_xml_dir, tmp_path):
        import sqlite3
        from sentinel.parsers.sms_parser import parse_sms_directory
        messages = parse_sms_directory(tmp_xml_dir)
        db_path  = tmp_path / 'test.db'
        export(db_path, messages=messages)
        export(db_path, messages=messages)  # Second import — should not duplicate
        conn  = sqlite3.connect(str(db_path))
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        conn.close()
        assert count == 5

    def test_schema_has_intent_table(self, tmp_path):
        import sqlite3
        db_path = tmp_path / 'test.db'
        export(db_path)
        conn    = sqlite3.connect(str(db_path))
        tables  = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        assert 'intent_results' in tables
        assert 'messages'       in tables
        assert 'calls'          in tables
        assert 'sentinel_meta'  in tables
