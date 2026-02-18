"""
sentinel/exporters/sqlite_exporter.py
Exports all data to SQLite — designed for M.I.N.D. Gateway pipeline.

SCHEMA DESIGN NOTES:
- messages and calls tables are the raw import layer
- intent_results is the analysis layer
- sentinel_meta stores run metadata and schema version
- Foreign key from intent_results.record_id → messages.id (soft reference)
- All timestamps stored as INTEGER milliseconds (Unix epoch * 1000)
  for consistency with Android SMS Backup & Restore format
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from sentinel.models.record import MessageRecord, CallRecord, IntentResult

if TYPE_CHECKING:
    from sentinel.aggregators.contact_aggregator import ContactProfile

logger = logging.getLogger(__name__)

SCHEMA_VERSION = '2.0'


def export(
    db_path:          Path,
    messages:         List[MessageRecord]  = None,
    calls:            List[CallRecord]     = None,
    intents:          List[IntentResult]   = None,
    contact_profiles: Optional[List["ContactProfile"]] = None,
    run_label:        str                  = '',
) -> Path:
    """
    Write all data to SQLite database.
    Safe to call multiple times — uses INSERT OR IGNORE on dedup keys.
    Returns db_path.
    """
    messages         = messages         or []
    calls            = calls            or []
    intents          = intents          or []
    contact_profiles = contact_profiles or []

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")   # Safe concurrent reads
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        _create_schema(conn)
        _write_messages(conn, messages)
        _write_calls(conn, calls)
        _write_intents(conn, intents)
        _write_contact_profiles(conn, contact_profiles)
        _write_meta(conn, messages, calls, intents, run_label)
        conn.commit()
        logger.info(
            f"SQLite export complete → {db_path}\n"
            f"  Messages: {len(messages)} | Calls: {len(calls)} | "
            f"Intent flags: {len(intents)}"
        )
    except Exception as e:
        conn.rollback()
        logger.error(f"SQLite export failed: {e}")
        raise
    finally:
        conn.close()

    return db_path


# ── SCHEMA ───────────────────────────────────────────────────

def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sentinel_meta (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_at          TEXT    NOT NULL,
            run_label       TEXT,
            schema_version  TEXT    NOT NULL,
            message_count   INTEGER DEFAULT 0,
            call_count      INTEGER DEFAULT 0,
            intent_count    INTEGER DEFAULT 0,
            notes           TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms    INTEGER NOT NULL,
            date_str        TEXT,
            direction       TEXT,
            contact_name    TEXT,
            phone_number    TEXT,
            msg_type        TEXT,
            body            TEXT,
            read            INTEGER DEFAULT 0,
            source_file     TEXT,
            UNIQUE(timestamp_ms, phone_number, msg_type)
        );

        CREATE TABLE IF NOT EXISTS calls (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms    INTEGER NOT NULL,
            date_str        TEXT,
            call_type       TEXT,
            contact_name    TEXT,
            phone_number    TEXT,
            duration_sec    INTEGER DEFAULT 0,
            duration_fmt    TEXT,
            source_file     TEXT,
            UNIQUE(timestamp_ms, phone_number)
        );

        CREATE TABLE IF NOT EXISTS intent_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            message_ts_ms   INTEGER NOT NULL,
            date_str        TEXT,
            direction       TEXT,
            contact_name    TEXT,
            phone_number    TEXT,
            msg_type        TEXT,
            body            TEXT,
            source_file     TEXT,

            kw_categories   TEXT,    -- JSON array
            kw_severity     TEXT,
            confirmed       INTEGER DEFAULT 0,
            ai_categories   TEXT,    -- JSON array
            ai_severity     TEXT,
            flagged_quote   TEXT,
            context_summary TEXT,
            context_before  TEXT,    -- JSON array
            context_after   TEXT,    -- JSON array
            llm_model       TEXT,
            detection_mode  TEXT,

            UNIQUE(message_ts_ms, phone_number)
        );

        -- Indexes for M.I.N.D. Gateway query patterns
        CREATE INDEX IF NOT EXISTS idx_msg_ts       ON messages(timestamp_ms);
        CREATE INDEX IF NOT EXISTS idx_msg_phone    ON messages(phone_number);
        CREATE INDEX IF NOT EXISTS idx_msg_contact  ON messages(contact_name);
        CREATE INDEX IF NOT EXISTS idx_call_ts      ON calls(timestamp_ms);
        CREATE INDEX IF NOT EXISTS idx_call_phone   ON calls(phone_number);
        CREATE INDEX IF NOT EXISTS idx_intent_ts    ON intent_results(message_ts_ms);
        CREATE INDEX IF NOT EXISTS idx_intent_phone ON intent_results(phone_number);
        CREATE INDEX IF NOT EXISTS idx_intent_sev   ON intent_results(ai_severity);

        CREATE TABLE IF NOT EXISTS contact_profiles (
            phone_number       TEXT PRIMARY KEY,
            contact_name       TEXT,
            total_messages     INTEGER DEFAULT 0,
            total_calls        INTEGER DEFAULT 0,
            total_flags        INTEGER DEFAULT 0,
            flag_rate          REAL DEFAULT 0.0,
            high_count         INTEGER DEFAULT 0,
            medium_count       INTEGER DEFAULT 0,
            low_count          INTEGER DEFAULT 0,
            risk_score        REAL DEFAULT 0.0,
            risk_label        TEXT DEFAULT 'LOW',
            category_breakdown TEXT,
            first_contact_ms   INTEGER,
            last_contact_ms    INTEGER,
            escalation_trend   TEXT DEFAULT 'UNKNOWN',
            relationship_tags  TEXT,
            generated_at       TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_contact_risk ON contact_profiles(risk_score DESC);
    """)


# ── WRITERS ──────────────────────────────────────────────────

def _write_messages(conn: sqlite3.Connection, messages: List[MessageRecord]) -> None:
    if not messages:
        return
    rows = [
        (
            m.timestamp_ms, m.date_str, m.direction,
            m.contact_name, m.phone_number, m.msg_type,
            m.body, int(m.read), m.source_file,
        )
        for m in messages
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO messages
        (timestamp_ms, date_str, direction, contact_name,
         phone_number, msg_type, body, read, source_file)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, rows)
    logger.debug(f"Wrote {len(rows)} message rows")


def _write_calls(conn: sqlite3.Connection, calls: List[CallRecord]) -> None:
    if not calls:
        return
    rows = [
        (
            c.timestamp_ms, c.date_str, c.call_type,
            c.contact_name, c.phone_number,
            c.duration_sec, c.duration_fmt, c.source_file,
        )
        for c in calls
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO calls
        (timestamp_ms, date_str, call_type, contact_name,
         phone_number, duration_sec, duration_fmt, source_file)
        VALUES (?,?,?,?,?,?,?,?)
    """, rows)
    logger.debug(f"Wrote {len(rows)} call rows")


def _write_intents(conn: sqlite3.Connection, intents: List[IntentResult]) -> None:
    if not intents:
        return
    rows = [
        (
            r.timestamp_ms,
            r.date_str,
            r.direction,
            r.contact_name,
            r.phone_number,
            r.msg_type,
            r.body,
            r.source_file,
            json.dumps(r.kw_categories),
            r.kw_severity,
            int(r.confirmed),
            json.dumps(r.ai_categories),
            r.ai_severity,
            r.flagged_quote,
            r.context_summary,
            json.dumps(r.context_before),
            json.dumps(r.context_after),
            r.llm_model,
            r.detection_mode,
        )
        for r in intents
    ]
    conn.executemany("""
        INSERT OR REPLACE INTO intent_results
        (message_ts_ms, date_str, direction, contact_name, phone_number,
         msg_type, body, source_file, kw_categories, kw_severity,
         confirmed, ai_categories, ai_severity, flagged_quote,
         context_summary, context_before, context_after,
         llm_model, detection_mode)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    logger.debug(f"Wrote {len(rows)} intent rows")


def _write_contact_profiles(conn: sqlite3.Connection, profiles: List) -> None:
    """Write contact profiles to contact_profiles table."""
    if not profiles:
        return
    rows = [
        (
            p.phone_number, p.contact_name, p.total_messages, p.total_calls,
            p.total_flags, p.flag_rate, p.high_count, p.medium_count, p.low_count,
            p.risk_score, p.risk_label, json.dumps(p.category_breakdown),
            p.first_contact_ms, p.last_contact_ms, p.escalation_trend,
            json.dumps(p.relationship_tags), p.generated_at,
        )
        for p in profiles
    ]
    conn.executemany("""
        INSERT OR REPLACE INTO contact_profiles
        (phone_number, contact_name, total_messages, total_calls,
         total_flags, flag_rate, high_count, medium_count, low_count,
         risk_score, risk_label, category_breakdown, first_contact_ms,
         last_contact_ms, escalation_trend, relationship_tags, generated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, rows)
    logger.debug(f"Wrote {len(rows)} contact profile rows")


def _write_meta(
    conn:      sqlite3.Connection,
    messages:  List[MessageRecord],
    calls:     List[CallRecord],
    intents:   List[IntentResult],
    run_label: str,
) -> None:
    conn.execute("""
        INSERT INTO sentinel_meta
        (run_at, run_label, schema_version, message_count, call_count, intent_count)
        VALUES (?,?,?,?,?,?)
    """, (
        datetime.now().isoformat(),
        run_label or 'sentinel-run',
        SCHEMA_VERSION,
        len(messages),
        len(calls),
        len(intents),
    ))
