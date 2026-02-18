# Privacy Policy
### mINd Suite | Nous Loop Solutions

*Last updated: February 2025*

---

## The Short Version

Your data stays on your device.
We do not collect it, transmit it, sell it, or analyze it.
We never will.

---

## The Full Version

### What Data mINd Suite Processes

mINd Suite processes the following data types locally on your device:

- SMS and MMS message content and metadata
- Call log records (numbers, duration, timestamps)
- Phone contact information
- Phone call audio recordings (mINd-VAULt only)
- Email content (mINd-VAULt only, with explicit user setup)

### Where Your Data Goes

Nowhere.

All processing — including AI analysis via Ollama — runs entirely
on your device. No message content, contact information, call recordings,
or analysis results are transmitted to any external server, including
servers operated by Nous Loop Solutions.

### What We Collect

Nothing.

Nous Loop Solutions operates no servers that receive user data.
We have no analytics platform. We have no telemetry system.
We do not know how many people use this software, where they are,
or what they do with it. We designed it that way intentionally.

### Third-Party Services

**Ollama:** The local LLM runtime runs entirely on your device.
Ollama does not transmit your data externally during inference.
Verify at: https://ollama.com/privacy

**Google Drive (optional):** If you choose to back up your SQLite
database to Google Drive, that data is governed by Google's Privacy
Policy. This is an optional, user-initiated action. The app does not
automatically sync to Drive.

**Google Contacts (optional):** If you enable contact enrichment,
the app reads your Google Contacts locally via the Android Contacts
Provider API. Contact data is stored in your local vault.db only.

**SMS Backup & Restore:** The XML backup files this app imports
are created by SMS Backup & Restore (Ritchie Apps). Their privacy
policy governs that app's behavior, not ours.

### Permissions We Request and Why

| Permission | Why |
|---|---|
| READ_SMS | To read incoming messages for intent analysis |
| RECEIVE_SMS | To process new messages in real time |
| READ_CALL_LOG | To import call log data |
| READ_CONTACTS | To match messages to contact names |
| RECORD_AUDIO | To transcribe phone calls (mINd-VAULt, user-initiated only) |
| READ_EXTERNAL_STORAGE | To read XML backup files from Drive folder |
| WRITE_EXTERNAL_STORAGE | To write the local SQLite database |
| BIND_ACCESSIBILITY_SERVICE | To display reply suggestions above keyboard |

We request only what we need. We use each permission only for
the stated purpose.

### Data Retention

Your data is retained in the local SQLite database (`vault.db`)
on your device for as long as you choose to keep it. Deleting the
app or the database file removes all locally stored data.

We retain nothing because we receive nothing.

### Children's Privacy

This software is not directed at children under 13.
It is designed for adults navigating complex communication situations.

### Legal Proceedings

If you use mINd Suite output in legal proceedings, consult your
attorney. AI-generated intent classifications are probabilistic
inferences, not legal conclusions. We make no representations
about the admissibility of any output in any jurisdiction.

### Changes to This Policy

If this policy changes in a way that affects user privacy negatively,
we will document it in the DIVERGENCE_LEDGER before the change
takes effect, not after.

We will not change the core commitment: your data stays on your device.

### Contact

GitHub Issues: https://github.com/nousloopsolutions/mINd-SENTinel
For privacy concerns specifically, open an issue titled [PRIVACY].

---

*Your data is yours. We built it that way on purpose.*

— Nous Loop Solutions, Minnesota
