# mINd-SENTinel · Nous Loop Solutions

> *Engineered for the Divergent. Enjoyed by the Mean.*

Offline SMS & call log intent analyzer — part of the **M.I.N.D. Gateway** pipeline.
100% on-device. No data leaves your machine.

---

## What's in this repo

| Path | Description |
|------|-------------|
| `sentinel/` | Core Python package — parsers, detectors, exporters |
| `sentinel/uplifts/` | Uplift extractor — mines positive messages from your database |
| `looking_glass/` | The Looking Glass — rotating quotes + search + filter |
| `run_uplifts.py` | Convenience script — replaces old `extract_uplifts.py` |
| `tests/` | Full test suite — 62 tests, parsers + detectors + uplift engine |

---

## Quick Start

```bash
pip install -r requirements.txt

# Step 1 — Parse XML backups and build database
python -m sentinel.cli \
  --xml-dir  ./backups \
  --output   sentinel.db \
  --keyword-only

# Step 2 — Extract uplifting messages with auto-tags
python run_uplifts.py \
  --db     sentinel.db \
  --output looking_glass/uplifts.json \
  --top    50

# Step 3 — Open looking_glass/index.html in your browser
#           Paste uplifts.json contents into PERSONAL_UPLIFTS_DATA, or
#           drag-and-drop the JSON file into the app.
```

---

## CLI Reference

### sentinel (full pipeline)

```
python -m sentinel.cli [OPTIONS]

Required:
  --xml-dir / -d        Directory with sms-*.xml and calls-*.xml
  --output  / -o        Output SQLite database (default: sentinel.db)

Analysis:
  --keyword-only / -k   Skip AI — keyword detection only (no Ollama required)
  --model    / -m       Ollama model (default: llama3:8b-instruct)
  --ollama-host         Ollama host URL (default: http://localhost:11434)
  --context-window      Context messages before/after (default: 2)

Filters:
  --sms-only            Parse SMS/MMS only
  --calls-only          Parse call logs only

Uplifts (combined pipeline):
  --extract-uplifts / -u     Mine positive messages after analysis
  --uplifts-output           Output JSON path (default: uplifts.json)
  --uplifts-top              Max uplifts to export (default: 50)

Utility:
  --list-models         List available Ollama models
  --run-label           Label for this run (stored in DB)
  --verbose / -v        Debug logging
```

### run_uplifts.py (standalone uplift extraction)

```
python run_uplifts.py [OPTIONS]

Required:
  --db                  Path to sentinel.db

Options:
  --output              Output JSON path (default: uplifts.json)
  --top                 Max uplifts to export (default: 50)
  --min-score           Minimum sentiment score (default: 4)
  --min-length          Minimum message length (default: 10)
  --max-length          Maximum message length (default: 160)
  --contact-filter      Only extract from contacts matching this string
                        Example: --contact-filter "Mom"
  --sender-only         Received messages only (default, kept for compat)
  --all-directions      Include sent messages as well
```

---

## The Looking Glass

Open `looking_glass/index.html` in any browser.

**Features:**
- Rotating manifesto quotes interleaved with personal uplifts
- **Search** — free text across message bodies and author names, with inline highlight
- **Filter chips** — click any tag to filter. Multiple chips = AND logic.
- **Tag badges** on each quote — click to filter by that tag instantly
- **∞ Uplift** reactions tracked via shared storage
- **Block sender** — removes author from rotation permanently

**To load your uplifts:**
1. Run `run_uplifts.py` to generate `uplifts.json`
2. Either paste the JSON array into `PERSONAL_UPLIFTS_DATA` at the top of the script block, or drag-and-drop the file into the app.

---

## Auto-Tags

The extractor produces these tag types automatically:

| Layer | Tags |
|-------|------|
| Sentiment | `love`, `pride`, `gratitude`, `encouragement`, `affirmation`, `warmth`, `joy` |
| Relationship | `mom`, `dad`, `child`, `partner`, `friend`, `family` |
| Info | `milestone`, `decision`, `date-time`, `location` |
| Custom | Edit `CUSTOM_TAGS` dict in `sentinel/uplifts/extractor.py` |

Custom tags are pre-populated with neurodivergent/IEP/recovery context. Edit to match your use case.

---

## Schema v2.0

Tables: `messages`, `calls`, `intent_results`, `sentinel_meta`

Timestamps: Unix epoch milliseconds (`INTEGER`).
Direction: `'Received'` / `'Sent'` (capital first letter — matches SMS Backup & Restore format).

---

## Changelog

| Version | Changes |
|---------|---------|
| v2.2 | `--contact-filter` flag, `--sender-only` backward compat, CUSTOM_TAGS populated, 62-test suite |
| v2.1 | Auto-tags, sentiment weights, search + filter in Looking Glass |
| v2.0 | `iterparse` streaming (OOM fix), call log record cap removed, uplift extractor moved to package |
| v1.0 | Initial release — keyword + AI pipeline, SQLite export |

---

## Known Pending

- Manual review of HIGH-severity keyword flags recommended before legal use
- Ollama AI confirmation (Phase 2) requires local Ollama install — keyword-only mode works without it

---

## Privacy

All processing is local. No network calls during analysis.
The Looking Glass stores user preferences in `localStorage` — no external servers.

`.db` files and `uplifts.json` are in `.gitignore` — personal data is never committed.

---

## Legal

AI-generated intent labels are probabilistic inferences.
Do not present as legal conclusions without attorney review.

---

*The Mean is No One. · Nous Loop Solutions · Minnesota LLC*
