"""
sentinel/detectors/keyword_detector.py
Phase 1 detection — pure Python, zero dependencies, fully offline.
Scans all messages against keyword dictionaries and returns candidates
for Phase 2 AI analysis. Can also run standalone (no LLM required).
"""

from typing import Dict, List, Tuple
from sentinel.models.record import MessageRecord, IntentResult

# ── KEYWORD DICTIONARIES ─────────────────────────────────────
# Extend these freely. Keys become category labels in output.

KEYWORD_MAP: Dict[str, List[str]] = {

    'INSULT': [
        'stupid', 'idiot', 'dumb', 'worthless', 'pathetic', 'loser',
        'moron', 'useless', 'garbage', 'trash', 'disgusting', 'failure',
        'incompetent', 'ignorant', 'ugly', 'hate you', 'shut up',
        'you never', 'you always', 'you are the problem', 'typical you',
        'piece of work', 'embarrassment', 'joke', 'waste of',
    ],

    'THREAT': [
        'you will regret', 'i will make sure', 'watch yourself',
        'you better', 'or else', 'i will destroy', 'see what happens',
        'i will take', 'you will lose', "ill take the kids",
        "i'll take the kids", 'take everything', 'lawyer', 'sue you',
        'court', 'restraining order', 'call the police', 'report you',
        'expose you', 'tell everyone', 'you have no idea what',
        'make your life', "won't get away",
    ],

    'MANIPULATION': [
        'after everything i', 'you never care', 'only think of yourself',
        'nobody else would', 'look what you made', 'you made me do',
        'if you loved me', 'you owe me', 'i gave up everything',
        'you always do this', 'this is your fault', 'you ruined',
        'because of you', 'how could you', 'you should feel',
        'stop playing victim', 'you imagined', 'did not happen',
        'that never happened', 'you are crazy', 'you are insane',
        'you are overreacting', 'so sensitive', 'too emotional',
        'no one will believe', 'no one believes you',
    ],

    'CUSTODY': [
        'custody', 'visitation', 'parenting time', 'the kids', 'our kids',
        'my kids', 'the children', 'our children', 'pickup', 'drop off',
        'drop-off', 'pick up', 'pick-up', 'school', 'daycare',
        'child support', 'guardian', 'parenting plan', 'holiday',
        'court order', 'modification', 'contempt', 'guardian ad litem',
        'gal ', 'mediator', 'mediation', 'custody hearing', 'judge',
        'attorney', 'supervised visit', 'unsupervised', 'physical custody',
        'legal custody', 'primary residence',
    ],

    'POSITIVE': [
        'i love you', 'love you', 'i appreciate', 'thank you',
        "i'm sorry", 'im sorry', 'proud of you', 'you are amazing',
        'you are great', 'i miss you', 'thinking of you', 'i care',
        'you matter', 'well done', 'good job', 'i support',
        'here for you', 'i understand', 'i believe you',
        'you are doing great', 'so grateful',
    ],
}

# Severity precedence (highest wins when multiple categories match)
SEVERITY_RANK = {
    'THREAT':       3,
    'INSULT':       2,
    'MANIPULATION': 2,
    'CUSTODY':      1,
    'POSITIVE':     0,
}


def scan_messages(
    messages:       List[MessageRecord],
    context_window: int = 2,
) -> List[IntentResult]:
    """
    Scan all messages. Returns IntentResult for every keyword match.
    context_window: how many messages before/after (same contact) to include.
    """
    results: List[IntentResult] = []

    # Build per-contact message index for context window lookup
    contact_index: Dict[str, List[int]] = {}
    for i, msg in enumerate(messages):
        key = msg.phone_number or msg.contact_name
        contact_index.setdefault(key, []).append(i)

    for i, msg in enumerate(messages):
        body_lower = msg.body.lower()
        if not body_lower.strip():
            continue

        matched: List[str] = []
        for category, keywords in KEYWORD_MAP.items():
            for kw in keywords:
                if kw in body_lower:
                    matched.append(category)
                    break

        if not matched:
            continue

        severity = _highest_severity(matched)

        # Context window — same contact only
        contact_key  = msg.phone_number or msg.contact_name
        peer_indices = contact_index.get(contact_key, [])
        pos          = peer_indices.index(i) if i in peer_indices else -1

        before: List[str] = []
        after:  List[str] = []

        if pos >= 0:
            for b in peer_indices[max(0, pos - context_window): pos]:
                m = messages[b]
                before.append(f"[{m.direction}] {m.body[:200]}")
            for a in peer_indices[pos + 1: pos + 1 + context_window]:
                m = messages[a]
                after.append(f"[{m.direction}] {m.body[:200]}")

        results.append(IntentResult(
            record_id      = i,
            timestamp_ms   = msg.timestamp_ms,
            date_str       = msg.date_str,
            direction      = msg.direction,
            contact_name   = msg.contact_name,
            phone_number   = msg.phone_number,
            msg_type       = msg.msg_type,
            body           = msg.body,
            source_file    = msg.source_file,
            kw_categories  = matched,
            kw_severity    = severity,
            confirmed      = False,         # Phase 2 sets this
            context_before = before,
            context_after  = after,
            detection_mode = 'KEYWORD',
        ))

    return results


def _highest_severity(categories: List[str]) -> str:
    best = max((SEVERITY_RANK.get(c, 0) for c in categories), default=0)
    if best >= 3: return 'HIGH'
    if best >= 2: return 'MEDIUM'
    return 'LOW'
