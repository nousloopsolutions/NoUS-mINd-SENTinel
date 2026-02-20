# JULES AGENT DIRECTIVES — mINd-SENTinel
# Version: 2026-02-20
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

## 3–9. [Rest of directives — Phase 0.3, Ollama, Privacy, Contact patterns, Scale, Feature completion, Reporting format]

*(Full content as provided by Architect; this file is the canonical reference for the repo.)*
