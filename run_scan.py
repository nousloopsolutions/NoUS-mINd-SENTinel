import sys
from pathlib import Path
from sentinel.parsers.sms_parser import parse_sms_directory
from sentinel.parsers.call_parser import parse_call_directory
from sentinel.detectors.intent_detector import run_full_analysis
from sentinel.llm.ollama_adapter import OllamaAdapter
from sentinel.aggregators.contact_aggregator import build_contact_profiles

import sqlite3, json

XML_DIR = Path(r"G:\My Drive\Chat Message Backup")
DB      = Path(r"G:\My Drive\mINd-SENTinel\test-output.db")
ADDRESS = "+16125550001"
MODEL   = "llama3.1:8b"

print(f"Parsing XML from {XML_DIR}...")
msgs  = parse_sms_directory(XML_DIR)
calls = parse_call_directory(XML_DIR)

msgs  = [m for m in msgs  if m.phone_number == ADDRESS]
calls = [c for c in calls if c.phone_number == ADDRESS]
print(f"Filtered to {ADDRESS}: {len(msgs)} msgs, {len(calls)} calls")

print(f"Running AI analysis with {MODEL} — this will take several minutes...")
llm = OllamaAdapter(model=MODEL)
if not llm.is_available():
    print("WARNING: Ollama unavailable — falling back to keyword-only")
    llm = None
intents = run_full_analysis(msgs, llm=llm)
print(f"Intents flagged: {len(intents)}")

for i in intents:
    print(f"  {i.ai_severity:6s}  {i.body[:80]}")

print("\nBuilding contact profile...")
contact_rels = {}
try:
    from sentinel.uplifts.extractor import CONTACT_RELATIONSHIPS
    contact_rels = CONTACT_RELATIONSHIPS
except ImportError:
    pass
profiles = build_contact_profiles(msgs, calls, intents, contact_relationships=contact_rels)
for p in profiles:
    print(f"  {p.risk_label} {round(p.risk_score,1)} {p.contact_name}")

print("\nWriting to DB...")
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

# Update intent results
rows = [(
    json.dumps(r.kw_categories), r.kw_severity, int(r.confirmed),
    json.dumps(r.ai_categories), r.ai_severity, r.flagged_quote,
    r.context_summary, json.dumps(r.context_before), json.dumps(r.context_after),
    r.llm_model, r.detection_mode,
    r.timestamp_ms, r.phone_number
) for r in intents]

conn.executemany("""
    UPDATE intent_results SET
        kw_categories=?, kw_severity=?, confirmed=?,
        ai_categories=?, ai_severity=?, flagged_quote=?,
        context_summary=?, context_before=?, context_after=?,
        llm_model=?, detection_mode=?
    WHERE message_ts_ms=? AND phone_number=?
""", rows)

# Update contact profile
for p in profiles:
    conn.execute("""
        INSERT OR REPLACE INTO contact_profiles
        (phone_number, contact_name, total_messages, total_calls,
         total_flags, flag_rate, high_count, medium_count, low_count,
         risk_score, risk_label, category_breakdown, first_contact_ms,
         last_contact_ms, escalation_trend, relationship_tags, generated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        p.phone_number, p.contact_name, p.total_messages, p.total_calls,
        p.total_flags, p.flag_rate, p.high_count, p.medium_count, p.low_count,
        p.risk_score, p.risk_label, json.dumps(p.category_breakdown),
        p.first_contact_ms, p.last_contact_ms, p.escalation_trend,
        json.dumps(p.relationship_tags), p.generated_at
    ))

conn.commit()
conn.close()
print("Done.")
