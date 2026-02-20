# JULES AGENT DIRECTIVES — mINd-SENTinel
# Version: 2026-02-20.1
# Authority: Nous Loop Solutions / Sovereign Architect
# Read this file completely before executing any task.

---

## 0. SESSION START PROTOCOL (MANDATORY — EVERY SESSION)

Before reading any task queue or writing any code, complete this checklist:

- [ ] Confirm active repository is `mINd-SENTinel`
- [ ] Confirm active task queue is the mINd-SENTinel queue only
- [ ] If any task references `nous-hub`, `nous-vault`, `sAId-hEARd`, or `M.I.N.D. Gateway` — STOP. Those tasks belong in their own repos. Do not execute them here.
- [ ] Verify the CLI is functional before running any parser tasks
- [ ] Check for BOM/encoding issues on any input file before parsing

**This is the repo where the queue drift incident occurred (2026-02-xx).** Jules previously executed M.I.N.D. Gateway tasks from the wrong queue while in this repo. That must not happen again. If a task in the queue references a different product, flag it to the Architect before doing anything.

---

## 1. PROJECT IDENTITY

**Repository:** mINd-SENTinel
**Owner:** Nous Loop Solutions LLC (Minnesota)
**Lead Developer:** Jules (AI Agent)
**Architect:** Brent Hovland
**Product:** Offline SMS and call log intent analyzer for legal documentation in family court situations

**Mission:** Privacy-first, on-device analysis. No cloud dependency. Legal-grade output.

---

## 2. PRODUCT SCOPE

mINd-SENTinel does ONE thing: analyze SMS/call log exports for intent patterns relevant to family court documentation.

**In scope:**
- Android SMS/call log export parsing (handle BOM, UTF-8, UTF-16 variants)
- Contact-level pattern aggregation (frequency delta, temporal clustering, semantic drift, keyword severity trajectory)
- Intent classification via Ollama (local inference only)
- Severity scoring
- Legal documentation output

**Out of scope — do not implement here:**
- Biosignal processing (belongs in nous-hub VDS_10000_CORE)
- Vector search or Vectorize integration (belongs in nous-hub)
- SGR or AEAD (belongs in nous-hub VDS_40000_SECURITY)
- Any feature from M.I.N.D. Gateway or sAId-hEARd

---

## 3. PHASE 0.3 TASKS — CLOSED

**Phase 0.3 — mINd-SENTinel queue fix — CLOSED (2026-02-20, Architect confirmed)**

The following tasks were authorized for Phase 0.3; they are now closed. Current authorized work is Phase 4.2 (Instance C). Historical task list:

**[0.3a] Verify active repository and task queue**
- Confirm you are in mINd-SENTinel repo
- Confirm no cross-repo tasks are in the active queue
- Report findings to Architect before proceeding

**[0.3b] Fix CLI update failure**
- Identify the CLI command or module causing the update failure
- Fix and verify CLI runs cleanly end-to-end
- Document the fix with a brief comment explaining the root cause

**[0.3c] Fix SMS parser BOM/encoding issue**
- Parser is failing on file read — likely BOM (byte order mark) on UTF-16 or UTF-8-BOM exports
- Fix: detect encoding automatically, strip BOM if present, fall back gracefully
- Test against at least one UTF-8, one UTF-8-BOM, and one UTF-16 sample
- Report which export formats are now confirmed working

**Completion report format:**
```
[0.3a] Queue verification — DONE
[0.3b] CLI fix — DONE / BLOCKED (reason)
[0.3c] SMS parser encoding fix — DONE / BLOCKED (reason)
  - Confirmed working formats: [list]
  - Known unsupported formats: [list]
Rollback: [git command]
Privacy note: [what data touches this code]
```

---

## 4. OLLAMA INTEGRATION RULES

Ollama is the only inference runtime for this product. No cloud LLM calls.

- Pass text strings to Ollama's local API endpoint
- Do not manage Ollama's runtime, model weights, or internal state
- Do not import PyTorch or any ML framework directly — Ollama handles that
- Input to Ollama: sanitized SMS/call log text only
- Output from Ollama: intent classification and severity score
- Log: operation counts and latency only. Never log message content.

---

## 5. PRIVACY RULES — LEGAL DOCUMENTATION CONTEXT

This product processes communications that may be used as evidence in family court. The privacy standard is higher than a consumer app.

**Absolute rules:**
- No message content written to logs under any condition
- No contact names or phone numbers written to logs
- Severity scores and pattern metadata are the only persistable outputs
- All local storage is encrypted at rest (AES-256-GCM minimum)
- No network calls during analysis — fully offline pipeline

**Legal integrity requirement:**
- Output reports must be reproducible from the same input
- Record the Ollama model version used for each analysis run
- Store input file hash alongside output — enables verification that output matches input

---

## 6. CONTACT-LEVEL PATTERN AGGREGATION — SPEC

These are the pattern types the analyzer must detect per contact:

| Pattern | Signal | Relevance |
|---|---|---|
| Frequency delta | Message rate change over time window | Escalation indicator |
| Temporal clustering | Messages concentrated in narrow time bands | Coercion/pressure indicator |
| Response latency exploitation | Short messages sent when response window closes | Pressure tactic indicator |
| Semantic drift | Vocabulary/topic shift over time | Grooming indicator |
| Keyword severity trajectory | Escalating severity in flagged keyword usage | Escalation confirmation |

Each contact gets a risk profile. Risk profiles feed the legal documentation export.

---

## 7. SCALE TARGET

- 10,000+ messages without cloud dependency
- All processing on-device via Ollama
- No index creation, no vector database — this is not a search product
- Performance target: full 10k message analysis under 5 minutes on mid-range Android hardware

---

## 8. FEATURE COMPLETION STANDARD

No feature is "done" unless it includes:
1. Tests (including malformed input, BOM variants, empty files)
2. Rollback plan (documented in PR description)
3. Privacy note (what data touches this code, what is logged, what is not)

---

## 9. REPORTING FORMAT

```
[TASK ID] Description — DONE / PENDING / BLOCKED
- What was implemented
- Test status
- Confirmed working input formats (for parser tasks)
- Rollback path
- Privacy note
- Gate status
```

Blockers reported immediately, not at end of session summary.
