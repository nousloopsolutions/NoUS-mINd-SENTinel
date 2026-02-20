# DIVERGENCE_LEDGER
### mINd-SENTinel | Nous Loop Solutions

---

> This document records known failures, false positives, design mistakes,
> and limitations in mINd-SENTinel. It is not a bug tracker.
> It is a public record of honest accounting.
> Updated as issues are discovered — not buried when they are inconvenient.

---

## FORMAT

Each entry follows this structure:

```
### [DATE] — [TITLE]
**Type:** Bug / False Positive / Design Mistake / Limitation / Known Gap
**Status:** Open / Resolved / Accepted / Investigating
**Impact:** Who is affected and how
**What happened:** Plain English description
**What we did:** Response or resolution
**Lesson:** What this teaches us
```

---

## ACTIVE ENTRIES

### 2026-02-20 — call_parser.py encoding (UTF-16 / UTF-8-BOM)
**Type:** Bug — Resolved
**Status:** Resolved
**Impact:** Users with calls-*.xml exported as UTF-16 or UTF-8-BOM (Android export format varies)
**What happened:** call_parser.py used basic UTF-8 only; sms_parser.py had BOM/UTF-16 handling from Phase 0.3c. calls-*.xml with UTF-16 or UTF-8-BOM could mis-decode or fail.
**What we did:** Aligned call_parser.py with sms_parser.py: _read_xml_text() with BOM detection and UTF-16 fallback. Implemented in Phase 4.2 per Architect Decision 1 (before scorer touches data). Tests: test_call_parser_utf8_standard, test_call_parser_utf8_bom, test_call_parser_utf16_bom.
**Lesson:** Parsers for the same export family (SMS Backup & Restore) must share encoding handling so court-admissible output is consistent across SMS and call logs.

---

### 2025-02-17 — Keyword False Positive Rate Unknown
**Type:** Known Gap
**Status:** Open
**Impact:** All users running keyword-only mode
**What happened:** The keyword dictionaries were built from general
knowledge of manipulation and abuse patterns, not from validated
clinical or forensic linguistic research. False positive rate on
real-world data has not been formally measured.
**What we did:** Built two-phase architecture so Ollama AI confirms
keyword candidates before flagging. Keyword-only mode clearly labeled
as unconfirmed.
**Lesson:** Intent detection without ground truth validation is inference,
not classification. AI confirmation reduces but does not eliminate error.
The user must remain the final judge.

---

### 2025-02-17 — Step 1 Bug: SMS Parser Searched calls- Files
**Type:** Bug — Resolved
**Status:** Resolved
**Impact:** Users of the original Google Apps Script version
**What happened:** The Google Apps Script Step 1 function contained
`n.indexOf('calls-')` instead of `n.indexOf('sms-')`. This caused
Step 1 to import call log records into the SMS sheet instead of
SMS messages. Step 2 was also searching for calls- so both steps
imported call logs and SMS was never imported.
**What we did:** Fixed the prefix filter in Step 1 to correctly
search for `sms-` files. Added unit tests to prevent regression.
**Lesson:** Two functions with near-identical code and one character
difference in a string literal. Code review and automated tests
catch what eyes miss.

---

### 2025-02-17 — MAX_BYTES Limit Too Low in Apps Script
**Type:** Bug — Resolved
**Status:** Resolved
**Impact:** Users with multi-year SMS backup files
**What happened:** Original MAX_BYTES was set to 900,000 bytes (900KB).
Multi-year SMS Backup & Restore files are typically 5-50MB. This caused
all large backup files to be silently skipped with no user notification
beyond a count in the alert.
**What we did:** Raised MAX_BYTES to 45,000,000 (45MB). Added explicit
logging of skipped large files.
**Lesson:** Default limits should be set based on real-world file sizes,
not arbitrary round numbers. Silent skipping is worse than loud failure.

---

### 2025-02-17 — Slow Scan on Google Drive Mounted Path
**Type:** Known Limitation
**Status:** Accepted
**Impact:** Windows users with XML files in Google Drive sync folder
**What happened:** Parsing 21 XML files from a Google Drive mounted path
(G:\My Drive\) took approximately 30+ minutes due to Drive sync I/O
overhead. Same files on local SSD would take ~3 minutes.
**What we did:** Documented. Recommended switching SMS Backup & Restore
to single rolling file instead of daily snapshots. Long-term fix is
mINd-VAULt maintaining its own local SQLite database.
**Lesson:** File I/O on network-mounted or cloud-synced paths is
unpredictably slow. Production pipeline should always target local storage.

---

### 2025-02-17 — Daily Backup Files Are Mostly Redundant
**Type:** Design Observation
**Status:** Accepted
**Impact:** Users with daily SMS Backup & Restore snapshots
**What happened:** Daily full snapshot backups create massive redundancy.
21 files containing ~7,760-7,981 records each — approximately 95% overlap
between consecutive files. Deduplication handles this correctly but wastes
significant processing time.
**What we did:** Deduplication implemented on (timestamp_ms, phone_number,
msg_type). Documented recommendation to switch to rolling single file.
**Lesson:** Incremental backup is architecturally superior to full snapshots
for this use case. mINd-VAULt will implement incremental writes natively.

---

### 2025-02-17 — AI Intent Labels Are Not Legal Evidence
**Type:** Known Limitation — Permanent
**Status:** Accepted — will never be resolved, by design
**Impact:** All users, especially those in legal proceedings
**What happened:** N/A — this is a permanent architectural limitation
**What we did:** Legal disclaimer embedded in CLI output, PHILOSOPHY.md,
LICENSE, and README. Every analysis run prints the disclaimer.
**Lesson:** Probabilistic inference cannot be presented as factual
determination. The disclaimer is not legal cover — it is honest
communication about what the tool can and cannot do.

---

## RESOLVED ENTRIES

See Active Entries above — all current entries include resolution status.

---

## HOW TO ADD AN ENTRY

If you find a failure, false positive, or design mistake:

1. Open an issue on GitHub with the title `[LEDGER] — description`
2. Include: what happened, who it affects, reproduction steps
3. We will add it to this document within 48 hours
4. Resolution will be documented when it occurs

We do not close ledger entries to make the project look better.
Resolved entries stay in the record permanently.

---

*"The measure of a tool is not that it never fails.*
*It is that it is honest about when it does."*

— Nous Loop Solutions
