"""
sentinel/scorer — Ollama severity scoring for Phase 4.2c.

Privacy: No raw message content in logs. Severity only in output.
"""

from sentinel.scorer.ollama_scorer import (
    SEVERITY_AMBIGUOUS,
    score_message,
    score_messages,
)

__all__ = [
    "SEVERITY_AMBIGUOUS",
    "score_message",
    "score_messages",
]
