"""
sentinel/uplifts/extractor.py — Nous Loop Solutions v2.2
Mines mINd-SENTinel SQLite database for positive/uplifting messages.
Produces uplifts.json with auto-tags for The Looking Glass web interface.

Tag layers:
  - Sentiment   : pride, love, gratitude, encouragement, affirmation, warmth, joy
  - Relationship: mom, dad, child, friend, partner, family
  - Info        : milestone, decision, date-time, location
  - Custom      : CUSTOM_TAGS dict below — add your own keyword → tag mappings

Usage (standalone):
    python -m sentinel.uplifts.extractor --db sentinel.db --output uplifts.json

    # Backward-compatible flags still work:
    python -m sentinel.uplifts.extractor --db sentinel.db --sender-only --top 50

Usage (via sentinel CLI):
    python -m sentinel.cli --xml-dir ./backups --output sentinel.db --extract-uplifts

Convenience script at repo root:
    python run_uplifts.py --db sentinel.db
"""

import sqlite3
import json
import argparse
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONTACT RELATIONSHIPS — Maps contact names to relationship tags.
# Used by contact_aggregator for risk profiles. Values are lists
# to support multiple tags per contact. Case-insensitive match.
# VERIFY: Update to match your actual relationships.
# ─────────────────────────────────────────────────────────────
CONTACT_RELATIONSHIPS: dict = {
    "Tiffany Hovland": ["ex-wife"],
    "Jaxon Hovland":   ["child"],
    "Jaxon":           ["child"],
}

# ─────────────────────────────────────────────────────────────
# CUSTOM TAGS — Add your own keyword → tag mappings here.
# Format: "keyword phrase" : "tag-name"
# All matching is case-insensitive substring.
# ─────────────────────────────────────────────────────────────
CUSTOM_TAGS: dict = {
    # ── Neurodivergent / Special Ed context ──
    "iep":             "milestone",
    "evaluation":      "milestone",
    "accommodation":   "milestone",
    "progress":        "milestone",
    "improvement":     "milestone",
    "breakthrough":    "milestone",
    "reading level":   "milestone",
    "test scores":     "milestone",

    # ── Recovery / Healing ──
    "therapy":         "healing",
    "counseling":      "healing",
    "doing better":    "healing",
    "feeling better":  "healing",
    "healing":         "healing",
    "recovering":      "healing",
    "sober":           "healing",
    "clean":           "healing",

    # ── Support / Community ──
    "we're here":      "support",
    "here for you":    "support",
    "lean on me":      "support",
    "not alone":       "support",
    "got your back":   "support",
    "standing by":     "support",

    # ── Add your own below ──
    # "school":        "milestone",
    # "new job":       "milestone",
    # "birthday":      "milestone",
}

# ── SENTIMENT SCORING ────────────────────────────────────────

KEYWORDS_HIGH = [
    "love you", "love u", "i love", "proud of you", "proud of u",
    "thank you", "thank u", "thanks so much", "really appreciate",
    "you're amazing", "you are amazing", "you're incredible",
    "you're the best", "you are the best", "best dad", "best mom",
    "miss you", "miss u", "i miss you", "can't wait to see you",
    "you did it", "you made it", "so happy for you",
    "you're so strong", "you are so strong", "believe in you",
    "i believe in you", "so proud", "mean the world",
    "you matter", "you're enough", "you are enough",
    "grateful for you", "lucky to have you",
]

KEYWORDS_MED = [
    "thank", "appreciate", "great job", "good job", "well done",
    "nice work", "awesome", "fantastic", "wonderful", "beautiful",
    "amazing", "incredible", "brilliant", "smart", "funny",
    "you're right", "you were right", "good point", "makes sense",
    "happy", "glad", "excited", "can't wait", "looking forward",
    "you got this", "you can do it", "hang in there",
    "thinking of you", "thought of you", "hope you're ok",
    "hope you feel better", "feel better", "take care",
    "sweet", "kind", "thoughtful", "generous", "caring",
    "good morning", "good night", "sleep well", "have a good",
    "have fun", "enjoy", "hope it goes well",
]

AMPLIFIERS = ["really", "so", "very", "truly", "always", "forever", "absolutely"]

EXCLUSIONS = [
    "attorney", "lawyer", "court", "custody", "order", "legal",
    "you need to", "you have to", "you must", "you better",
    "you always", "you never", "your fault", "blame you",
    "told you", "stop it", "leave me", "whatever",
    "don't want", "don't care", "i can't deal",
]

EMOJI_PATTERN = re.compile(
    r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF'
    r'\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF'
    r'\u2764\u2665\u2660\u2666\u2663]'
)

# ── TAG DEFINITIONS ──────────────────────────────────────────

SENTIMENT_TAGS: dict = {
    "love":          ["love you", "love u", "i love", "miss you", "miss u",
                      "mean the world", "lucky to have"],
    "pride":         ["proud", "you did it", "you made it", "so proud",
                      "well done", "great job", "good job", "you matter",
                      "you're enough", "you are enough"],
    "gratitude":     ["thank", "appreciate", "grateful", "means a lot"],
    "encouragement": ["believe in you", "you got this", "you can do it",
                      "hang in there", "so strong", "keep going", "don't give up"],
    "affirmation":   ["amazing", "incredible", "brilliant", "smart", "talented",
                      "gifted", "capable", "you're the best", "you are the best"],
    "warmth":        ["thinking of you", "thought of you", "take care",
                      "hope you're ok", "feel better", "sweet", "kind",
                      "thoughtful", "caring", "generous"],
    "joy":           ["happy", "excited", "glad", "wonderful", "fantastic",
                      "awesome", "can't wait", "looking forward", "so happy for"],
}

RELATIONSHIP_TAGS: dict = {
    "mom":     ["mom", "mother", "mama", "mum", "mommy", "ma "],
    "dad":     ["dad", "father", "papa", "daddy", "pa "],
    "child":   ["kid", "son", "daughter", "baby", "little one",
                "my child", "my boy", "my girl"],
    "partner": ["babe", "baby", "honey", "sweetheart", "husband", "wife",
                "my love", "darling", "lover"],
    "friend":  ["friend", "bestie", "buddy", "pal", "bff",
                "my person", "homie", "teammate"],
    "family":  ["family", "sister", "brother", "sibling", "grandma",
                "grandpa", "aunt", "uncle", "cousin", "sis ", "bro "],
}

INFO_TAGS: dict = {
    "milestone": [
        "birthday", "happy birthday", "anniversary", "graduation",
        "promoted", "promotion", "wedding", "engaged", "new job",
        "new home", "new baby", "first day", "congrats", "congratulations",
    ],
    "decision":  ["decided", "confirmed", "agreed", "let's", "we're going",
                  "it's settled", "plan is", "going with"],
    "date-time": ["on monday", "on tuesday", "on wednesday", "on thursday",
                  "on friday", "on saturday", "on sunday",
                  " at noon", " at night", " am ", " pm ", "o'clock",
                  "tonight", "tomorrow", "this weekend", "next week"],
    "location":  ["at home", "come over", "meet at", "pick up", "drop off",
                  "restaurant", "airport", "school", "hospital",
                  "downtown", "at the park", "our place", "your place"],
}

CATEGORY_MAP = [
    (['love', 'miss', 'matter', 'enough'],           'Love & Connection'),
    (['thank', 'appreciate', 'grateful'],             'Gratitude'),
    (['amazing', 'incredible', 'best', 'brilliant'],  'Affirmation'),
    (['proud', 'did it', 'made it', 'well done'],     'Pride'),
    (['you got this', 'believe', 'strong'],            'Encouragement'),
]


# ── TAG ENGINE ───────────────────────────────────────────────

def _apply_tag_group(lower: str, tag_group: dict) -> List[str]:
    return [tag for tag, kws in tag_group.items() if any(kw in lower for kw in kws)]


def tag_message(body: str, contact_name: str = '') -> List[str]:
    """Return sorted list of auto-tags. Covers sentiment, relationship, info, custom."""
    if not body:
        return []
    lower = (body + ' ' + contact_name).lower()
    tags  = set()

    tags.update(_apply_tag_group(lower, SENTIMENT_TAGS))
    tags.update(_apply_tag_group(lower, INFO_TAGS))

    # Relationship — body + contact name heuristic
    for tag, keywords in RELATIONSHIP_TAGS.items():
        if any(kw in lower for kw in keywords):
            tags.add(tag)
        name_lower = contact_name.lower()
        if tag in name_lower:
            tags.add(tag)

    # Custom
    for keyword, custom_tag in CUSTOM_TAGS.items():
        if keyword.lower() in lower:
            tags.add(custom_tag)

    return sorted(tags)


def sentiment_weight(score: int, max_score: int = 40) -> float:
    return round(min(score / max_score, 1.0), 3)


# ── SCORING ──────────────────────────────────────────────────

def score_message(body: str):
    """Return (score, matched_keyword). Score 0 = exclude."""
    if not body or len(body.strip()) < 5:
        return 0, ''
    lower = body.lower()
    if any(ex in lower for ex in EXCLUSIONS):
        return 0, ''

    score = 0; matched = ''
    for kw in KEYWORDS_HIGH:
        if kw in lower:
            score += 10; matched = matched or kw
    for kw in KEYWORDS_MED:
        if kw in lower:
            score += 4;  matched = matched or kw
    for amp in AMPLIFIERS:
        if amp in lower:
            score += 1

    length = len(body.strip())
    if length < 15:  score = max(0, score - 3)
    if length > 300: score = max(0, score - 4)

    score += min(len(EMOJI_PATTERN.findall(body)) * 2, 6)
    return score, matched


def _categorize(keyword: str) -> str:
    kw = keyword.lower()
    for words, cat in CATEGORY_MAP:
        if any(w in kw for w in words):
            return cat
    return 'A Moment of Light'


def _clean_body(body: str) -> str:
    body = body.strip()
    for p in ['[MMS message]', '[Attachment]', '(no subject)', '[MMS — media only]']:
        body = body.replace(p, '').strip()
    body = re.sub(r'\s+', ' ', body)
    if len(body) > 180:
        body = body[:177].rsplit(' ', 1)[0] + '…'
    return body


def _display_name(contact_name: str, phone_number: str) -> str:
    name = (contact_name or '').strip()
    if name:
        return name
    num = (phone_number or '').strip()
    return f"Someone who cares (+{num[-4:]})" if len(num) >= 4 else "Someone who cares"


# ── MAIN EXTRACTOR ───────────────────────────────────────────

def extract_uplifts(
    db_path:        str,
    output_path:    str  = 'uplifts.json',
    min_len:        int  = 10,
    max_len:        int  = 160,
    received_only:  bool = True,
    top:            int  = 50,
    min_score:      int  = 4,
    contact_filter: Optional[str] = None,
) -> list:
    """
    Mine the mINd-SENTinel database for uplifting messages.

    Args:
        contact_filter: If set, only include messages from contacts whose
                        name or phone number contains this string (case-insensitive).

    Returns the list of uplift dicts (also writes JSON to output_path).
    Raises FileNotFoundError if db_path does not exist.
    """
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    conn = sqlite3.connect(str(db))
    conn.row_factory = sqlite3.Row

    cols     = [d[1] for d in conn.execute('PRAGMA table_info(messages)').fetchall()]
    required = {'timestamp_ms', 'phone_number', 'contact_name', 'body', 'direction'}
    missing  = required - set(cols)
    if missing:
        conn.close()
        raise ValueError(
            f"Schema missing columns: {missing}. "
            f"Re-run sentinel to regenerate the DB."
        )

    query  = """
        SELECT id, timestamp_ms, phone_number, contact_name, body, direction, msg_type
        FROM messages
        WHERE body IS NOT NULL
          AND length(trim(body)) >= ?
          AND length(trim(body)) <= ?
    """
    params = [min_len, max_len]

    if received_only:
        query += " AND direction = 'Received'"

    if contact_filter:
        query += " AND (lower(contact_name) LIKE ? OR phone_number LIKE ?)"
        pattern = f"%{contact_filter.lower()}%"
        params += [pattern, pattern]

    query += " ORDER BY timestamp_ms DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    logger.info(f"Scanning {len(rows):,} candidate messages…")

    scored = []
    for row in rows:
        body = row['body'] or ''
        score, kw = score_message(body)
        if score >= min_score:
            name = _display_name(row['contact_name'], row['phone_number'])
            scored.append({
                'score':   score,
                'keyword': kw,
                'body':    _clean_body(body),
                'name':    name,
                'contact': row['contact_name'] or '',
                'date_ms': row['timestamp_ms'],
            })

    scored.sort(key=lambda x: x['score'], reverse=True)

    seen    = set()
    deduped = []
    for item in scored:
        key = item['body'][:40].lower().strip()
        if key not in seen:
            seen.add(key)
            deduped.append(item)

    top_items = deduped[:top]
    logger.info(
        f"Found {len(scored):,} positive → "
        f"{len(deduped):,} unique → exporting top {len(top_items)}"
    )

    output = []
    for item in top_items:
        try:
            date_str = datetime.fromtimestamp(item['date_ms'] / 1000).strftime('%b %Y')
        except Exception:
            date_str = ''

        tags = tag_message(item['body'], item['contact'])
        output.append({
            'text':             item['body'],
            'author':           item['name'],
            'date':             date_str,
            'category':         _categorize(item['keyword']),
            'tags':             tags,
            'sentiment_weight': sentiment_weight(item['score']),
            'score':            item['score'],
            'type':             'personal',
        })

    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    logger.info(f"Exported {len(output)} uplifts → {out_path}")
    return output


# ── CLI ───────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    parser = argparse.ArgumentParser(
        prog        = 'sentinel-uplifts',
        description = 'Nous Loop — Uplift Extractor v2.2\n'
                      'Mines mINd-SENTinel DB for positive messages.',
        formatter_class = argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--db',             required=True,  help='Path to sentinel.db')
    parser.add_argument('--output',         default='uplifts.json')
    parser.add_argument('--min-length',     type=int, default=10)
    parser.add_argument('--max-length',     type=int, default=160)
    parser.add_argument('--top',            type=int, default=50)
    parser.add_argument('--min-score',      type=int, default=4)
    parser.add_argument('--contact-filter', default=None,
                        help='Only extract from contacts matching this string')

    # Direction flags — both styles supported for backward compat
    direction_group = parser.add_mutually_exclusive_group()
    direction_group.add_argument(
        '--sender-only', action='store_true',
        help='Only include received messages (default behavior, kept for compatibility)',
    )
    direction_group.add_argument(
        '--all-directions', action='store_true',
        help='Include sent messages as well as received',
    )

    args = parser.parse_args()

    # --sender-only and default both mean received_only=True
    received_only = not args.all_directions

    print(f"\n  Nous Loop — Uplift Extractor v2.2")
    print(f"  ∞ Mining {args.db}")
    if args.contact_filter:
        print(f"  ∞ Filtering by contact: '{args.contact_filter}'")
    print()

    try:
        results = extract_uplifts(
            db_path        = args.db,
            output_path    = args.output,
            min_len        = args.min_length,
            max_len        = args.max_length,
            received_only  = received_only,
            top            = args.top,
            min_score      = args.min_score,
            contact_filter = args.contact_filter,
        )

        from collections import Counter
        all_tags   = [t for r in results for t in r.get('tags', [])]
        tag_counts = Counter(all_tags).most_common(12)

        print(f"  ✓ Exported {len(results)} uplifts → {args.output}")
        if tag_counts:
            print(f"\n  Top tags:")
            for tag, n in tag_counts:
                bar = '▓' * min(n, 20)
                print(f"    {tag:<18} {bar} {n}")
        print()

    except (FileNotFoundError, ValueError) as e:
        print(f"  [ERROR] {e}")
        raise SystemExit(1)


if __name__ == '__main__':
    main()
