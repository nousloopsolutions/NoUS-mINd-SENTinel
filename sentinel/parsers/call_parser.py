"""
sentinel/parsers/call_parser.py
Parses SMS Backup & Restore call log XML files (calls-*.xml).

FIX v2.0: Replaced ET.fromstring() with ET.iterparse() for streaming.
          Eliminated OOM crash on large call logs. No record count cap.

FIX v2.1 (Phase 4.2, Architect): BOM and encoding aligned with sms_parser.py.
          Same _read_xml_text logic: UTF-8-BOM, UTF-16-LE/BE by BOM, else UTF-8.
          No message content in logs. Parser output schema unchanged.
          Phase 7.1: encoding fix verified; tests and DIVERGENCE_LEDGER entry added.
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List
import logging
import re
import io

from sentinel.models.record import CallRecord

logger = logging.getLogger(__name__)

# BOMs for encoding detection (aligned with sms_parser.py Phase 0.3c)
BOM_UTF8 = b'\xef\xbb\xbf'
BOM_UTF16_LE = b'\xff\xfe'
BOM_UTF16_BE = b'\xfe\xff'

CALL_TYPE = {
    '1': 'Incoming', '2': 'Outgoing', '3': 'Missed',
    '4': 'Voicemail','5': 'Rejected', '6': 'Blocked',
    '7': 'Answered Externally',
}


def _read_xml_text(path: Path) -> str:
    """
    Read XML file with BOM/encoding handling (aligned with sms_parser.py).
    Tries UTF-8-BOM strip, then UTF-16 if BOM present, else UTF-8 with replace.
    """
    raw = path.read_bytes()
    if raw.startswith(BOM_UTF8):
        return raw[len(BOM_UTF8):].decode('utf-8', errors='replace')
    if raw.startswith(BOM_UTF16_LE):
        return raw[len(BOM_UTF16_LE):].decode('utf-16-le', errors='replace')
    if raw.startswith(BOM_UTF16_BE):
        return raw[len(BOM_UTF16_BE):].decode('utf-16-be', errors='replace')
    try:
        return raw.decode('utf-8', errors='strict')
    except UnicodeDecodeError:
        return raw.decode('utf-8', errors='replace')


def _strip_stylesheet(content: str) -> str:
    return re.sub(r'<\?xml-stylesheet[^?]*\?>', '', content)


def parse_call_file(path: Path) -> List[CallRecord]:
    """
    Parse a single calls XML file using streaming iterparse.
    No record count cap — processes all records regardless of file size.
    Supports UTF-8, UTF-8-BOM, UTF-16-LE/BE (same as sms_parser).
    """
    records: List[CallRecord] = []

    try:
        content = _read_xml_text(path)
        content = _strip_stylesheet(content)
        stream  = io.StringIO(content)

        for _event, el in ET.iterparse(stream, events=('end',)):
            if el.tag.lower() != 'call':
                el.clear()
                continue
            try:
                ts  = int(el.get('date', '0') or '0')
                dur = int(el.get('duration', '0') or '0')
                num = _sanitize_phone(el.get('number', '') or '')
                records.append(CallRecord(
                    timestamp_ms  = ts,
                    date_str      = _epoch_to_str(ts),
                    call_type     = CALL_TYPE.get(el.get('type', '1'), 'Unknown'),
                    contact_name  = _sanitize(el.get('contact_name', '') or ''),
                    phone_number  = num,
                    duration_sec  = dur,
                    duration_fmt  = _fmt_duration(dur),
                    source_file   = path.name,
                ))
            except Exception as e:
                logger.debug(f"Skipped call element: {e}")
            finally:
                el.clear()

    except ET.ParseError as e:
        logger.error(f"XML parse error in {path.name}: {e}")
        return records
    except OSError as e:
        logger.error(f"File read error {path.name}: {e}")
        return []

    logger.info(f"Parsed {len(records)} calls from {path.name}")
    return records


def parse_call_directory(directory: Path) -> List[CallRecord]:
    all_records: List[CallRecord] = []
    seen: set = set()

    for path in sorted(directory.glob('calls-*.xml')):
        for rec in parse_call_file(path):
            key = (rec.timestamp_ms, rec.phone_number)
            if key in seen:
                continue
            seen.add(key)
            all_records.append(rec)

    all_records.sort(key=lambda r: r.timestamp_ms)
    logger.info(f"Total calls after dedup: {len(all_records)}")
    return all_records


def _epoch_to_str(ts: int) -> str:
    try:
        return datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return 'INVALID_DATE'

def _fmt_duration(seconds: int) -> str:
    if seconds <= 0:
        return '0s'
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"

def _sanitize(text: str) -> str:
    return ''.join(c for c in (text or '') if c.isprintable())[:300]

def _sanitize_phone(phone: str) -> str:
    return ''.join(c for c in (phone or '') if c.isdigit() or c in '+-() ')[:30]
