"""
sentinel/detectors/intent_detector.py
Phase 2 orchestrator. Takes keyword candidates, sends to LLM,
merges results. Falls back to keyword-only if LLM unavailable.

Zero-Vector Shield: Ghost records (empty/whitespace body or zero-norm)
are filtered out before analysis to avoid noise and null injections.
"""

import logging
from typing import List, Optional, Callable

from sentinel.detectors.keyword_detector import scan_messages
from sentinel.llm.base import LLMAdapter
from sentinel.models.record import MessageRecord, IntentResult

logger = logging.getLogger(__name__)


def _is_ghost_record(msg: MessageRecord) -> bool:
    """
    Norm-check: ignore ghost SMS/call records that would produce zero signal.
    Returns True if the record should be excluded from analysis.
    """
    body = (msg.body or "").strip()
    if not body:
        return True
    # Optional: exclude zero/negative timestamp (corrupt or placeholder)
    if msg.timestamp_ms <= 0:
        return True
    return False


def run_full_analysis(
    messages:       List[MessageRecord],
    llm:            Optional[LLMAdapter] = None,
    context_window: int                  = 2,
    progress_cb:    Optional[Callable]   = None,
) -> List[IntentResult]:
    """
    Full two-phase analysis pipeline.

    Phase 1: Keyword scan (always runs, offline, instant)
    Phase 2: LLM confirmation (skipped if llm=None or unavailable)

    progress_cb: optional callable(current, total, message) for CLI progress bar.
    Returns all confirmed IntentResults sorted by timestamp.
    """

    # ── ZERO-VECTOR SHIELD: drop ghost records ─────────────────
    non_ghost = [m for m in messages if not _is_ghost_record(m)]
    dropped = len(messages) - len(non_ghost)
    if dropped:
        logger.info(f"Zero-Vector Shield: excluded {dropped} ghost record(s).")
    messages = non_ghost
    if not messages:
        logger.info("No non-ghost messages — nothing to analyze.")
        return []

    # ── PHASE 1 ──────────────────────────────────────────────
    logger.info(f"Phase 1: Keyword scan across {len(messages)} messages...")
    candidates = scan_messages(messages, context_window=context_window)
    logger.info(f"Phase 1 complete: {len(candidates)} candidates flagged")

    if not candidates:
        logger.info("No candidates — nothing to analyze.")
        return []

    # ── LLM AVAILABILITY CHECK ────────────────────────────────
    use_llm = False
    if llm is not None:
        logger.info("Checking LLM availability...")
        if llm.is_available():
            use_llm = True
            logger.info(f"LLM available — Phase 2 will run AI confirmation.")
        else:
            logger.warning(
                "LLM unavailable — running keyword-only mode.\n"
                "All Phase 1 candidates will be marked confirmed=True.\n"
                "Start Ollama and re-run to get AI confirmation."
            )

    # ── PHASE 2 (or keyword-only fallback) ───────────────────
    results: List[IntentResult] = []
    total = len(candidates)

    for i, candidate in enumerate(candidates):

        if progress_cb:
            progress_cb(i + 1, total, f"Analyzing: {candidate.contact_name or candidate.phone_number}")

        if not use_llm:
            # Keyword-only: confirm all candidates as-is
            candidate.confirmed      = True
            candidate.ai_categories  = candidate.kw_categories
            candidate.ai_severity    = candidate.kw_severity
            candidate.flagged_quote  = candidate.body[:300]
            candidate.context_summary = (
                f"Keyword detection: {', '.join(candidate.kw_categories)}. "
                f"No LLM available for deeper analysis."
            )
            candidate.detection_mode = 'KEYWORD'
            results.append(candidate)
            continue

        # ── LLM ANALYSIS ─────────────────────────────────────
        response = llm.analyze(
            body           = candidate.body,
            direction      = candidate.direction,
            contact_name   = candidate.contact_name,
            kw_categories  = candidate.kw_categories,
            context_before = candidate.context_before,
            context_after  = candidate.context_after,
        )

        if response is None:
            # LLM call failed — fall back to keyword result
            logger.warning(f"LLM returned None for record {i} — using keyword result.")
            candidate.confirmed      = True
            candidate.ai_categories  = candidate.kw_categories
            candidate.ai_severity    = candidate.kw_severity
            candidate.flagged_quote  = candidate.body[:300]
            candidate.context_summary = "LLM call failed — keyword detection only."
            candidate.detection_mode = 'AI_FALLBACK'
            candidate.llm_model      = 'fallback'
            results.append(candidate)
            continue

        if not response.confirmed:
            # LLM dismissed as false positive — skip
            logger.debug(f"Record {i} dismissed by LLM (false positive).")
            continue

        # LLM confirmed — merge results
        candidate.confirmed      = True
        candidate.ai_categories  = response.categories
        candidate.ai_severity    = response.severity
        candidate.flagged_quote  = response.flagged_quote
        candidate.context_summary = response.context_summary
        candidate.llm_model      = response.model_used
        candidate.detection_mode = 'AI'
        results.append(candidate)

    logger.info(
        f"Analysis complete: {len(results)} confirmed / "
        f"{len(candidates)} candidates / "
        f"{len(candidates) - len(results)} dismissed as false positives"
    )

    results.sort(key=lambda r: r.timestamp_ms)
    return results
