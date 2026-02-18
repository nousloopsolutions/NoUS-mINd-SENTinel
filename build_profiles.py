import argparse
import json
import os
import sqlite3
from pathlib import Path
from sentinel.models.record import MessageRecord, CallRecord, IntentResult
from sentinel.aggregators.contact_aggregator import build_contact_profiles

parser = argparse.ArgumentParser()
parser.add_argument("--db", default=os.environ.get("SENTINEL_DB", r"G:\My Drive\mINd-SENTinel\test-output.db"))
args = parser.parse_args()
DB = Path(args.db)

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

msgs = [MessageRecord(
    timestamp_ms=r["timestamp_ms"], date_str=r["date_str"],
    direction=r["direction"], contact_name=r["contact_name"],
    phone_number=r["phone_number"], msg_type=r["msg_type"],
    body=r["body"], read=bool(r["read"]), source_file=r["source_file"]
) for r in conn.execute("SELECT * FROM messages").fetchall()]

calls = [CallRecord(
    timestamp_ms=r["timestamp_ms"], date_str=r["date_str"],
    call_type=r["call_type"], contact_name=r["contact_name"],
    phone_number=r["phone_number"], duration_sec=r["duration_sec"],
    duration_fmt=r["duration_fmt"], source_file=r["source_file"]
) for r in conn.execute("SELECT * FROM calls").fetchall()]

intents = [IntentResult(
    record_id=r["id"] if "id" in r.keys() else None,
    timestamp_ms=r["message_ts_ms"], date_str=r["date_str"],
    direction=r["direction"], contact_name=r["contact_name"],
    phone_number=r["phone_number"], msg_type=r["msg_type"],
    body=r["body"], source_file=r["source_file"],
    kw_categories=json.loads(r["kw_categories"] or "[]"),
    kw_severity=r["kw_severity"], confirmed=bool(r["confirmed"]),
    ai_categories=json.loads(r["ai_categories"] or "[]"),
    ai_severity=r["ai_severity"], flagged_quote=r["flagged_quote"],
    context_summary=r["context_summary"],
    context_before=json.loads(r["context_before"] or "[]"),
    context_after=json.loads(r["context_after"] or "[]"),
    llm_model=r["llm_model"], detection_mode=r["detection_mode"]
) for r in conn.execute("SELECT * FROM intent_results").fetchall()]

conn.row_factory = None
print(f"Loaded: {len(msgs)} msgs, {len(calls)} calls, {len(intents)} intents")

profiles = build_contact_profiles(msgs, calls, intents)
print(f"Profiles built: {len(profiles)}")
for p in profiles:
    print(p.risk_label, round(p.risk_score, 1), p.contact_name)

# Write profiles directly — bypasses old exporter
rows = [(
    p.phone_number, p.contact_name, p.total_messages, p.total_calls,
    p.total_flags, p.flag_rate, p.high_count, p.medium_count, p.low_count,
    p.risk_score, p.risk_label, json.dumps(p.category_breakdown),
    p.first_contact_ms, p.last_contact_ms, p.escalation_trend,
    json.dumps(p.relationship_tags), p.generated_at
) for p in profiles]

conn.executemany("""
    INSERT OR REPLACE INTO contact_profiles
    (phone_number, contact_name, total_messages, total_calls,
     total_flags, flag_rate, high_count, medium_count, low_count,
     risk_score, risk_label, category_breakdown, first_contact_ms,
     last_contact_ms, escalation_trend, relationship_tags, generated_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
""", rows)
conn.commit()
conn.close()
print("Done — profiles written to DB")
