# Contributing to mINd-SENTinel
### Nous Loop Solutions

---

Before contributing, read `PHILOSOPHY.md`. It is short.
Everything below flows from it.

---

## Who We Want

Contributors who have been failed by mainstream software.
Contributors who build tools they wish they'd had.
Contributors who understand that neurodivergent users are not
edge cases to be accommodated — they are the design target.

You do not need to be a professional developer.
You do not need to be neurodivergent.
You need to share the values in `PHILOSOPHY.md`.

---

## What We Will Not Merge

- Telemetry, analytics, or usage tracking of any kind
- Features that transmit user data to external servers without
  explicit user-initiated action
- Advertising hooks or monetization features
- Features that treat users as means rather than ends
- Code that removes or weakens the human-in-the-loop requirement
  for actions affecting real human relationships
- AI confidence scores presented as factual determinations

---

## Getting Started

```bash
# Fork the repo on GitHub
# Clone your fork
git clone https://github.com/YOUR_USERNAME/mINd-SENTinel.git
cd mINd-SENTinel

# Install in development mode
python -m pip install -e .

# Run the test suite — all 19 tests must pass before any PR
python -m pytest tests/ -v

# Make your changes on a feature branch
git checkout -b feature/your-description
```

---

## Pull Request Requirements

Every PR must include:

**1. Tests**
New functionality requires new tests.
Bug fixes require a test that would have caught the bug.
No exceptions.

**2. DIVERGENCE_LEDGER entry (if applicable)**
If your PR fixes a known failure, update `DIVERGENCE_LEDGER.md`.
If your PR introduces a known limitation, document it there.

**3. Privacy note**
One sentence in the PR description confirming your change
does not introduce any data transmission, logging of message
content, or external API calls without explicit user action.

**4. Rollback plan**
For any change that modifies the SQLite schema or file format,
document how existing databases will be migrated or remain
compatible.

---

## Code Standards

- Python 3.10+ only
- No required third-party dependencies for core functionality
- All parsers must handle malformed input gracefully — never crash
- All LLM calls must have a local fallback (keyword-only mode)
- Phone numbers and message content are never logged at INFO level
- Sanitize all user-provided input before processing

---

## Adding a New LLM Backend

Subclass `LLMAdapter` in `sentinel/llm/base.py`.
Implement `is_available()` and `analyze()`.
Add a test in `tests/` that mocks the backend.
Document hardware requirements in the class docstring.

---

## Reporting Issues

Open a GitHub issue with:
- What you expected to happen
- What actually happened
- Your platform (Windows / Linux / Termux)
- Python version (`python --version`)
- Anonymized example input if relevant (never paste real messages)

If the issue belongs in the DIVERGENCE_LEDGER, title it:
`[LEDGER] — description`

---

## A Note on AI-Assisted Contributions

This project was built with AI assistance and is transparent about that.
AI-assisted contributions are welcome — with the same standard applied
to all code: you are responsible for what you submit, AI-generated or not.

Do not submit code you do not understand.
The human is always in the loop. Including in code review.

---

*Built with AI. Owned by humans. Free forever.*
