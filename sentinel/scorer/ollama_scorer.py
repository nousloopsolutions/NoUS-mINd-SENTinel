"""
sentinel/scorer/ollama_scorer.py
Phase 4.2c — Ollama Severity Scorer.

Integrates Ollama for severity-only scoring on parsed messages.
Privacy: No raw message content in logs. Severity scores only. No PII in logs.
Malformed payload from Ollama → fail closed with SEVERITY_AMBIGUOUS.
"""

import logging
import time
from typing import List, Optional, Callable, TYPE_CHECKING

from sentinel.models.record import MessageRecord, IntentResult

if TYPE_CHECKING:
    from sentinel.llm.base import LLMAdapter

logger = logging.getLogger(__name__)

# Fail-closed severity when Ollama response is malformed or ambiguous (Phase 4.2, Architect)
SEVERITY_AMBIGUOUS = "AMBIGUOUS"

VALID_SEVERITIES = frozenset({"HIGH", "MEDIUM", "LOW"})


def _parse_severity_from_response(response_text: str) -> str:
    """
    Parse severity from Ollama JSON response. Fail closed.
    Returns a valid severity (HIGH/MEDIUM/LOW) or SEVERITY_AMBIGUOUS.
    Never raises — malformed payload → AMBIGUOUS.
    """
    import json
    try:
        clean = response_text.strip()
        if clean.startswith("```"):
            parts = clean.split("```")
            if len(parts) >= 2:
                clean = parts[1]
                if clean.startswith("json"):
                    clean = clean[4:]
        clean = clean.strip()
        data = json.loads(clean)
        raw = data.get("severity")
        if raw is None:
            return SEVERITY_AMBIGUOUS
        s = str(raw).strip().upper()
        if s in VALID_SEVERITIES:
            return s
        return SEVERITY_AMBIGUOUS
    except (json.JSONDecodeError, TypeError, AttributeError):
        return SEVERITY_AMBIGUOUS


def score_message(
    msg: MessageRecord,
    llm: "LLMAdapter",
    record_id: int = 0,
) -> IntentResult:
    """
    Score one message via Ollama. Returns IntentResult with ai_severity set.
    Malformed or missing severity in response → ai_severity = SEVERITY_AMBIGUOUS (fail closed).
    No message content logged.
    """
    result = IntentResult(
        record_id=record_id,
        timestamp_ms=msg.timestamp_ms,
        date_str=msg.date_str,
        direction=msg.direction,
        contact_name=msg.contact_name,
        phone_number=msg.phone_number,
        msg_type=msg.msg_type,
        body=msg.body,
        source_file=msg.source_file,
        kw_categories=[],
        kw_severity="LOW",
        confirmed=False,
        ai_categories=[],
        ai_severity=SEVERITY_AMBIGUOUS,
        llm_model="keyword-only",
        detection_mode="KEYWORD",
    )

    if not (msg.body or "").strip():
        result.ai_severity = SEVERITY_AMBIGUOUS
        result.detection_mode = "AI_FALLBACK"
        return result

    try:
        response = llm.analyze(
            body=msg.body,
            direction=msg.direction,
            contact_name=msg.contact_name,
            kw_categories=[],
            context_before=[],
            context_after=[],
        )
    except Exception:
        result.ai_severity = SEVERITY_AMBIGUOUS
        result.detection_mode = "AI_FALLBACK"
        result.llm_model = "fallback"
        return result

    if response is None:
        result.ai_severity = SEVERITY_AMBIGUOUS
        result.detection_mode = "AI_FALLBACK"
        result.llm_model = "fallback"
        return result

    raw_sev = getattr(response, "severity", None)
    if raw_sev and str(raw_sev).strip().upper() in VALID_SEVERITIES:
        severity = str(raw_sev).strip().upper()
    else:
        severity = _parse_severity_from_response(
            getattr(response, "raw_response", "") or ""
        )
    result.ai_severity = severity
    result.llm_model = getattr(response, "model_used", getattr(llm, "model", "ollama"))
    result.detection_mode = "AI" if severity != SEVERITY_AMBIGUOUS else "AI_FALLBACK"
    result.confirmed = severity != SEVERITY_AMBIGUOUS
    return result


def score_messages(
    messages: List[MessageRecord],
    llm: "LLMAdapter",
    record_id_fn: Optional[Callable[[MessageRecord, int], int]] = None,
    progress_cb: Optional[Callable[[int, int], None]] = None,
) -> List[IntentResult]:
    """
    Score a list of messages via Ollama. Returns IntentResults with ai_severity only.
    Logs operation count and latency only — never message content or PII.
    """
    if not messages:
        logger.info("Scorer: 0 messages — nothing to score.")
        return []

    start = time.perf_counter()
    results: List[IntentResult] = []
    total = len(messages)

    for i, msg in enumerate(messages):
        if progress_cb:
            progress_cb(i + 1, total)
        rid = record_id_fn(msg, i) if record_id_fn else 0
        results.append(score_message(msg, llm, record_id=rid))

    elapsed = time.perf_counter() - start
    logger.info(
        "Scorer complete: count=%s latency_sec=%.2f",
        len(results),
        elapsed,
    )
    return results
