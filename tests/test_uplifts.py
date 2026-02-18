"""
tests/test_uplifts.py
Unit tests for sentinel.uplifts — tag engine and extractor.
Uses a real in-memory SQLite database — no external files needed.
"""

import json
import sqlite3
import pytest
import tempfile
from pathlib import Path

from sentinel.uplifts.extractor import (
    score_message,
    tag_message,
    sentiment_weight,
    extract_uplifts,
    _clean_body,
    _categorize,
    _display_name,
)


# ── FIXTURES ─────────────────────────────────────────────────

UPLIFT_MESSAGES = [
    # (contact_name, phone, direction, body)
    ("Mom",     "+16125550001", "Received", "I'm so proud of you, you did it!"),
    ("Mom",     "+16125550001", "Received", "Love you so much sweetheart"),
    ("Friend",  "+16125550002", "Received", "You are amazing, keep going!"),
    ("Friend",  "+16125550002", "Received", "Thinking of you today hope you're ok"),
    ("Partner", "+16125550003", "Received", "Happy birthday babe, you mean the world to me"),
    ("Partner", "+16125550003", "Received", "I believe in you always"),
    ("Sent",    "+16125550001", "Sent",     "Thanks so much mom, love you"),
    ("Lawyer",  "+16125550004", "Received", "The attorney called about court custody order"),
    ("Nobody",  "+16125550005", "Received", "ok"),
]

@pytest.fixture
def uplifts_db(tmp_path):
    """Create a test SQLite database matching the sentinel schema."""
    db_path = tmp_path / "test_uplifts.db"
    conn    = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE messages (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp_ms INTEGER NOT NULL,
            date_str     TEXT,
            direction    TEXT,
            contact_name TEXT,
            phone_number TEXT,
            msg_type     TEXT,
            body         TEXT,
            read         INTEGER DEFAULT 0,
            source_file  TEXT,
            UNIQUE(timestamp_ms, phone_number, msg_type)
        )
    """)
    for i, (name, phone, direction, body) in enumerate(UPLIFT_MESSAGES):
        conn.execute(
            "INSERT INTO messages (timestamp_ms, date_str, direction, contact_name, phone_number, msg_type, body, read, source_file) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (1704067200000 + i * 60000, "2024-01-01", direction, name, phone, "SMS", body, 1, "test.xml")
        )
    conn.commit()
    conn.close()
    return db_path


# ── SCORE TESTS ───────────────────────────────────────────────

class TestScoreMessage:

    def test_high_keyword_scores_ten(self):
        score, kw = score_message("I love you so much")
        assert score >= 10
        assert kw != ''

    def test_exclusion_returns_zero(self):
        score, _ = score_message("Attorney court custody order")
        assert score == 0

    def test_emoji_boosts_score(self):
        base,  _ = score_message("Thank you")
        boost, _ = score_message("Thank you ❤️❤️")
        assert boost > base

    def test_very_short_message_penalized(self):
        score, _ = score_message("ok")
        assert score == 0

    def test_empty_body_returns_zero(self):
        score, _ = score_message("")
        assert score == 0

    def test_amplifier_adds_point(self):
        # "really" prepended to a MED keyword phrase adds +1 without breaking the match
        base, _ = score_message("thinking of you")
        amp,  _ = score_message("really thinking of you")
        assert amp > base

    def test_benign_message_no_score(self):
        score, _ = score_message("The weather is nice today.")
        assert score == 0


# ── TAG ENGINE TESTS ──────────────────────────────────────────

class TestTagMessage:

    def test_love_tag_detected(self):
        tags = tag_message("I love you so much")
        assert 'love' in tags

    def test_pride_tag_detected(self):
        tags = tag_message("I'm so proud of you")
        assert 'pride' in tags

    def test_gratitude_tag_detected(self):
        tags = tag_message("Thank you for everything")
        assert 'gratitude' in tags

    def test_mom_tag_from_body(self):
        tags = tag_message("Love you mom")
        assert 'mom' in tags

    def test_mom_tag_from_contact_name(self):
        tags = tag_message("I love you", contact_name="Mom")
        assert 'mom' in tags

    def test_partner_tag_detected(self):
        tags = tag_message("Miss you babe")
        assert 'partner' in tags

    def test_milestone_from_birthday(self):
        tags = tag_message("Happy birthday!")
        assert 'milestone' in tags

    def test_empty_body_returns_empty(self):
        tags = tag_message("")
        assert tags == []

    def test_tags_are_sorted(self):
        tags = tag_message("So proud of you mom, happy birthday, love you")
        assert tags == sorted(tags)

    def test_no_duplicate_tags(self):
        tags = tag_message("Love you love you love you")
        assert len(tags) == len(set(tags))

    def test_exclusion_body_still_tagged(self):
        # Tag engine doesn't filter — scoring does. Tags still apply.
        tags = tag_message("Court attorney custody")
        # Should not have sentiment tags, may have none or location
        assert 'love' not in tags
        assert 'pride' not in tags

    def test_encouragement_tag(self):
        tags = tag_message("You got this, I believe in you")
        assert 'encouragement' in tags

    def test_warmth_tag(self):
        tags = tag_message("Thinking of you today")
        assert 'warmth' in tags


# ── SENTIMENT WEIGHT TESTS ────────────────────────────────────

class TestSentimentWeight:

    def test_zero_score_is_zero(self):
        assert sentiment_weight(0) == 0.0

    def test_max_score_is_one(self):
        assert sentiment_weight(40) == 1.0

    def test_over_max_capped_at_one(self):
        assert sentiment_weight(100) == 1.0

    def test_mid_range(self):
        w = sentiment_weight(20)
        assert 0.4 < w < 0.6


# ── EXTRACTOR INTEGRATION TESTS ───────────────────────────────

class TestExtractUplifts:

    def test_basic_extraction(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out))
        assert len(results) > 0
        assert out.exists()

    def test_output_is_valid_json(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        extract_uplifts(str(uplifts_db), str(out))
        data = json.loads(out.read_text(encoding='utf-8'))
        assert isinstance(data, list)

    def test_each_record_has_required_fields(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out))
        for r in results:
            assert 'text'             in r
            assert 'author'           in r
            assert 'date'             in r
            assert 'category'         in r
            assert 'tags'             in r
            assert 'sentiment_weight' in r
            assert 'type'             in r
            assert r['type'] == 'personal'

    def test_tags_is_list(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out))
        for r in results:
            assert isinstance(r['tags'], list)

    def test_received_only_excludes_sent(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out), received_only=True)
        # "Sent" direction should be excluded
        authors = {r['author'] for r in results}
        # The sent message was from "Mom"'s number but direction=Sent
        # We can't perfectly test this without knowing author,
        # but score-filtered results should come from received messages
        for r in results:
            assert r['text'] != "Thanks so much mom, love you"

    def test_exclusion_filters_legal_messages(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out))
        texts = [r['text'] for r in results]
        assert not any('attorney' in t.lower() for t in texts)
        assert not any('custody'  in t.lower() for t in texts)

    def test_contact_filter(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(
            str(uplifts_db), str(out),
            contact_filter="Mom"
        )
        for r in results:
            assert 'mom' in r['author'].lower() or 'someone' in r['author'].lower()

    def test_top_limit_respected(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out), top=2)
        assert len(results) <= 2

    def test_missing_db_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            extract_uplifts(str(tmp_path / "nonexistent.db"), str(tmp_path / "out.json"))

    def test_bad_schema_raises(self, tmp_path):
        bad_db = tmp_path / "bad.db"
        conn   = sqlite3.connect(str(bad_db))
        conn.execute("CREATE TABLE messages (id INTEGER, text TEXT)")
        conn.commit(); conn.close()
        with pytest.raises(ValueError, match="Schema missing columns"):
            extract_uplifts(str(bad_db), str(tmp_path / "out.json"))

    def test_sentiment_weight_between_0_and_1(self, uplifts_db, tmp_path):
        out = tmp_path / "out.json"
        results = extract_uplifts(str(uplifts_db), str(out))
        for r in results:
            assert 0.0 <= r['sentiment_weight'] <= 1.0

    def test_deduplication(self, tmp_path):
        """Duplicate message bodies should appear only once."""
        db_path = tmp_path / "dedup.db"
        conn    = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE messages (
                id INTEGER PRIMARY KEY, timestamp_ms INTEGER,
                date_str TEXT, direction TEXT, contact_name TEXT,
                phone_number TEXT, msg_type TEXT, body TEXT,
                read INTEGER, source_file TEXT,
                UNIQUE(timestamp_ms, phone_number, msg_type)
            )
        """)
        # Insert same body twice from different contacts
        for i in range(3):
            conn.execute(
                "INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
                (i, 1704067200000 + i*1000, "2024-01-01", "Received",
                 f"Contact{i}", f"+1612555000{i}", "SMS",
                 "I love you so much", 1, "test.xml")
            )
        conn.commit(); conn.close()
        out     = tmp_path / "out.json"
        results = extract_uplifts(str(db_path), str(out))
        texts   = [r['text'] for r in results]
        assert len(texts) == len(set(texts))


# ── HELPER TESTS ─────────────────────────────────────────────

class TestHelpers:

    def test_clean_body_strips_mms_artifacts(self):
        body = _clean_body("[MMS message] Hello there  ")
        assert '[MMS message]' not in body
        assert body.startswith('Hello')

    def test_clean_body_truncates_long(self):
        long = "a " * 200
        result = _clean_body(long)
        assert len(result) <= 183  # 180 + ellipsis

    def test_display_name_uses_contact(self):
        assert _display_name("Mom", "+16125550001") == "Mom"

    def test_display_name_falls_back_to_phone(self):
        name = _display_name("", "+16125550001")
        assert "0001" in name

    def test_categorize_love(self):
        assert _categorize("love") == 'Love & Connection'

    def test_categorize_gratitude(self):
        assert _categorize("thank") == 'Gratitude'

    def test_categorize_default(self):
        assert _categorize("xyzabc") == 'A Moment of Light'
