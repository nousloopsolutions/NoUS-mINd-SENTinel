"""
sentinel/personalization.py
Builds personalized prompts from parsed messages, uplifts, media metadata, and audio transcripts.
Feeds mINd-REPly voice profiles and context-aware analysis.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def build_voice_context(db_path: Path, limit: int = 100) -> str:
    """
    Extract user's communication style from Sent messages.
    Returns a context string for personalized prompts.
    """
    if not db_path.exists():
        return ""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT body FROM messages
        WHERE direction = 'Sent' AND body IS NOT NULL AND length(trim(body)) > 5
        ORDER BY timestamp_ms DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    if not rows:
        return ""
    bodies = [r["body"] for r in rows]
    words = []
    for b in bodies:
        words.extend(b.split())
    vocab = Counter(w.lower() for w in words if len(w) > 2)
    top_words = [w for w, _ in vocab.most_common(50)]
    avg_len = sum(len(b.split()) for b in bodies) / max(len(bodies), 1)
    return (
        f"User's typical vocabulary (top words): {', '.join(top_words[:20])}. "
        f"Average sentence length: {avg_len:.1f} words. "
    )


def build_uplift_context(db_path: Path, limit: int = 20) -> str:
    """
    Extract uplifting phrases the user has received.
    Personalizes prompts with positive context.
    """
    try:
        from sentinel.uplifts.extractor import extract_uplifts
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp = f.name
        try:
            uplifts = extract_uplifts(db_path=str(db_path), output_path=tmp, top=limit)
            if not uplifts:
                return ""
            phrases = [u.get("text", "")[:80] for u in uplifts[:10] if u.get("text")]
            return f"Uplifting messages this user has received: {' | '.join(phrases)}. "
        finally:
            Path(tmp).unlink(missing_ok=True)
    except Exception as e:
        logger.debug(f"Uplift context failed: {e}")
        return ""


def build_audio_context(db_path: Path, limit: int = 5) -> str:
    """
    Extract context from call transcripts (recordings table).
    Returns summary for personalized prompts.
    """
    if not db_path.exists():
        return ""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("SELECT 1 FROM recordings LIMIT 1")
    except sqlite3.OperationalError:
        conn.close()
        return ""
    rows = conn.execute(
        """
        SELECT transcript, contact_name FROM recordings
        WHERE transcript IS NOT NULL AND length(trim(transcript)) > 20
        ORDER BY timestamp_ms DESC LIMIT ?
        """,
        (limit,),
    ).fetchall()
    conn.close()
    if not rows:
        return ""
    excerpts = [f"{r[1] or 'Unknown'}: {r[0][:100]}..." for r in rows]
    return f"Recent call transcripts (excerpts): {' | '.join(excerpts)}. "


def build_relationship_context(contact_relationships: Dict[str, List[str]]) -> str:
    """Format contact relationships for prompt context."""
    if not contact_relationships:
        return ""
    parts = [f"{k}: {', '.join(v)}" for k, v in contact_relationships.items()]
    return f"Key relationships: {'; '.join(parts)}. "


def build_personalized_system_prompt(
    db_path: Path,
    contact_relationships: Optional[Dict[str, List[str]]] = None,
    include_voice: bool = True,
    include_uplifts: bool = True,
    include_audio: bool = True,
) -> str:
    """
    Build a personalized system prompt from all available sources.
    Used to tailor LLM analysis to this user's context.
    """
    parts = [
        "You are a forensic communication analyst. "
        "Analyze messages for harmful, manipulative, or legally relevant intent. "
        "All analysis is probabilistic inference — not legal conclusions. "
    ]
    if include_voice:
        voice = build_voice_context(db_path)
        if voice:
            parts.append(f"USER CONTEXT: {voice}")
    if include_uplifts:
        uplift = build_uplift_context(db_path)
        if uplift:
            parts.append(f"POSITIVE CONTEXT: {uplift}")
    if include_audio:
        audio = build_audio_context(db_path)
        if audio:
            parts.append(f"AUDIO CONTEXT: {audio}")
    if contact_relationships:
        rel = build_relationship_context(contact_relationships)
        if rel:
            parts.append(rel)
    return " ".join(parts).strip()
