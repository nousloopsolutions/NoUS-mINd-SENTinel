# mINd Suite Roadmap
### Nous Loop Solutions

---

> Built for people who need tools designed for them, not population averages.
> "We're all some deviation from the mean."

---

## The Suite

Three repositories. One shared database. One philosophy.

```
mINd-SENTinel    what was SENT, seen from the INside
mINd-REPly       REPly with your voice, not your anxiety  
mINd-VAULt       your communications, VAULted and yours alone
```

Each app is independent. Together they form a complete
private communications intelligence system that runs
entirely on your hardware.

---

## mINd-SENTinel — Status: BETA

**What it does:** Analyzes SMS and call log backups for intent
patterns — manipulation, threats, insults, custody-relevant
communications, and positive messages.

**Current capability:**
- [x] SMS Backup & Restore XML parser (SMS + MMS)
- [x] Call log XML parser
- [x] Keyword detection — 5 categories, 3 severity levels
- [x] Ollama AI confirmation layer
- [x] SQLite output — M.I.N.D. Gateway compatible schema
- [x] Deduplication across overlapping backup files
- [x] Windows + Linux support
- [x] Kantian ethics constraint in prompt layer

**Next:**
- [ ] Termux (Android) install and test
- [ ] Google Play Store submission
- [ ] False positive rate measurement on real-world data
- [ ] Additional manipulation pattern categories
- [ ] Contact-level pattern aggregation (flag contacts, not just messages)
- [ ] Date range filtering in CLI
- [ ] Export to PDF for legal documentation

---

## mINd-REPly — Status: SCOPED

**What it does:** Learns your communication voice from your
message history. Suggests replies above your keyboard.
Auto-replies to confirmed spam and bots only.
All replies to real humans require your conscious approval.

**Architecture:**
- Android Accessibility Service — keyboard suggestion bar
- Ollama on-device — reply generation
- Voice profile built from your Sent messages in sentinel.db
- Kantian ethics layer — real humans always get human approval
- Spam/bot detection — auto-deflect with configurable responses

**Speech pattern learning:**
- Vocabulary matching — uses your words, not generic AI words
- Sentence length calibration — matches your natural rhythm
- Tone detection — casual vs formal based on recipient history
- Phrase learning — picks up expressions you use often
- Negative space — avoids words and phrases you never use

**Planned categories:**
- [ ] Spam deflection (auto)
- [ ] Bot deflection (auto)
- [ ] Aggressive solicitor deflection (auto)
- [ ] Emotional support suggestion (human approval)
- [ ] Conflict de-escalation suggestion (human approval)
- [ ] Custody coordination suggestion (human approval, extra caution)
- [ ] General reply suggestion (human approval)

---

## mINd-VAULt — Status: SCOPED

**What it does:** Your complete private communications archive.
Records, organizes, transcribes, and enriches everything —
locally, privately, permanently.

**Data sources:**
- [ ] SMS/MMS (via SMS Backup & Restore XML — bootstrap)
- [ ] SMS/MMS (live incremental — real time after bootstrap)
- [ ] Call logs (via XML — bootstrap)
- [ ] Call logs (live incremental — real time)
- [ ] Phone call audio (via ACR Plus integration)
- [ ] Phone call transcription (Ollama Whisper — local)
- [ ] Email (Gmail API — local storage only)

**Contact intelligence:**
- [ ] Person profiles built from communication history
- [ ] Sentiment trend over time per contact
- [ ] Communication frequency patterns
- [ ] Topic clustering per contact
- [ ] Google Contacts enrichment (read local, write local)
- [ ] Custom contact notes — context fields for important relationships

**Recording architecture (Minnesota — one party consent):**
- ACR Plus handles the recording (proven, tested on Z Fold 4)
- mINd-VAULt imports recordings automatically
- Ollama transcribes locally — no audio leaves device
- Transcripts linked to call log records in vault.db
- Sentinel runs intent analysis on transcripts

**Legal documentation mode:**
- Timestamped, immutable log entries
- Export to PDF with chain of custody notation
- Attorney-ready formatting
- Explicit AI-inference labeling on all analysis

---

## Shared Infrastructure

**vault.db — unified SQLite schema**
Single database format shared across all three apps.
Schema versioned in sentinel_meta table.
Migration path documented for every version change.

**Ollama — shared local LLM**
One Ollama instance serves all three apps.
Model recommendations by device RAM documented.
Z Fold 4 optimized for phi3:medium or llama3.1:8b.

**Ethics layer — shared constraint**
Kantian ethics prompt constraint embedded in every
AI call across all three apps. Not configurable.
Every person is an end. Never a means.

---

## Android Marketplace

**Target:** Google Play Store — Free, no in-app purchases

**Timeline:**
1. mINd-SENTinel — validate on real data → submit
2. mINd-REPly — build → beta test → submit
3. mINd-VAULt — build → beta test → submit
4. mINd Suite — unified app combining all three

**Google Play data safety declaration:**
All three apps declare: local processing only, no data
transmitted to external servers, no advertising, no analytics.
This is our strongest asset for approval, not a liability.

---

## What This Is Building Toward

A personal AI system that knows your communication history,
understands your voice, protects you from manipulation,
and helps you show up as your best self in difficult conversations —
running entirely on your phone, owned entirely by you,
free to anyone who needs it.

A cognitive prosthetic for the social-emotional challenges
that neurodivergent individuals navigate every day.

An extra sensory organ that makes the implicit explicit —
not to replace human judgment, but to support it.

---

## What This Will Never Be

- Subscription software
- A data collection platform
- A tool for surveilling people who have not harmed you
- A replacement for human connection
- Finished

---

*The roadmap grows with the community.*
*Open an issue to propose a feature.*
*Read PHILOSOPHY.md before you do.*

— Nous Loop Solutions, Minnesota
*Built with AI. Owned by humans. Free forever.*
