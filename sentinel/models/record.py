"""
sentinel/models/record.py
Shared dataclass schema. All parsers, detectors, and exporters
use these types. Do not add logic here — data only.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class MessageRecord:
    """Normalized SMS or MMS record."""
    timestamp_ms:  int
    date_str:      str
    direction:     str          # Received / Sent / Draft / Outbox
    contact_name:  str
    phone_number:  str
    msg_type:      str          # SMS / MMS
    body:          str
    read:          bool
    source_file:   str


@dataclass
class CallRecord:
    """Normalized call log record."""
    timestamp_ms:   int
    date_str:       str
    call_type:      str         # Incoming / Outgoing / Missed / Voicemail / Rejected / Blocked
    contact_name:   str
    phone_number:   str
    duration_sec:   int
    duration_fmt:   str         # e.g. "4m 32s"
    source_file:    str


@dataclass
class IntentResult:
    """Output of intent analysis for one message."""
    record_id:       int        # rowid in messages table
    timestamp_ms:    int
    date_str:        str
    direction:       str
    contact_name:    str
    phone_number:    str
    msg_type:        str
    body:            str
    source_file:     str

    # Detection outputs
    kw_categories:   List[str]  = field(default_factory=list)
    kw_severity:     str        = 'LOW'
    confirmed:       bool       = False
    ai_categories:   List[str]  = field(default_factory=list)
    ai_severity:     str        = 'LOW'
    flagged_quote:   str        = ''
    context_summary: str        = ''
    context_before:  List[str]  = field(default_factory=list)
    context_after:   List[str]  = field(default_factory=list)
    llm_model:       str        = 'keyword-only'
    detection_mode:  str        = 'KEYWORD'     # KEYWORD / AI / AI_FALLBACK
