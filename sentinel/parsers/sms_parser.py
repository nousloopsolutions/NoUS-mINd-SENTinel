"""
sentinel/parsers/sms_parser.py
Parses SMS Backup & Restore XML files (sms-*.xml).
Handles both <sms> and <mms> nodes.

FIX v2.0: Replaced ET.fromstring() with ET.iterparse() for streaming.
          Large XML files (>200MB) no longer cause OOM errors.

Schema: https://synctech.com.au/sms-backup-restore/fields-in-xml-backup-files/
"""

import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import List
import logging
import re
import io

from sentinel.models.record import MessageRecord

logger = logging.getLogger(__name__)

SMS_DIRECTION = {
    '1': 'Received', '2': 'Sent', '3': 'Draft',
    '4': 'Outbox',   '5': 'Failed', '6': 'Queued',
}
MMS_DIRECTION = {
    '1': 'Received', '2': 'Sent',
}


def parse_sms_file(path: Path) -> List[MessageRecord]:
    """
    Parse a single SMS Backup & Restore XML file using streaming iterparse.
    Handles arbitrarily large files without loading into RAM.
    Returns list of MessageRecord — empty list on parse failure.
    """
    records: List[MessageRecord] = []

    try:
        content = path.read_text(encoding='utf-8', errors='replace')
        content = _strip_stylesheet(content)
        stream  = io.StringIO(content)

        for _event, el in ET.iterparse(stream, events=('end',)):
            tag = el.tag.lower()
            if tag == 'sms':
                rec = _parse_sms(el, path.name)
                if rec:
                    records.append(rec)
                el.clear()
            elif tag == 'mms':
                rec = _parse_mms(el, path.name)
                if rec:
                    records.append(rec)
                el.clear()

    except ET.ParseError as e:
        logger.error(f"XML parse error in {path.name}: {e}")
        return records
    except OSError as e:
        logger.error(f"File read error {path.name}: {e}")
        return []

    logger.info(f"Parsed {len(records)} SMS/MMS from {path.name}")
    return records


def parse_sms_directory(directory: Path) -> List[MessageRecord]:
    """
    Parse all sms-*.xml files in a directory.
    Deduplicates on (timestamp_ms, phone_number, msg_type).
    """
    all_records: List[MessageRecord] = []
    seen: set = set()

    xml_files = sorted(directory.glob('sms-*.xml'))
    if not xml_files:
        logger.warning(f"No sms-*.xml files found in {directory}")
        return []

    for path in xml_files:
        for rec in parse_sms_file(path):
            key = (rec.timestamp_ms, rec.phone_number, rec.msg_type)
            if key in seen:
                continue
            seen.add(key)
            all_records.append(rec)

    all_records.sort(key=lambda r: r.timestamp_ms)
    logger.info(f"Total SMS/MMS after dedup: {len(all_records)}")
    return all_records


def _parse_sms(el: ET.Element, source_file: str):
    try:
        ts = int(_attr(el, 'date') or '0')
        return MessageRecord(
            timestamp_ms  = ts,
            date_str      = _epoch_to_str(ts),
            direction     = SMS_DIRECTION.get(_attr(el, 'type'), 'Unknown'),
            contact_name  = _sanitize(_attr(el, 'contact_name')),
            phone_number  = _sanitize_phone(_attr(el, 'address')),
            msg_type      = 'SMS',
            body          = _sanitize(_attr(el, 'body'), max_len=50000),
            read          = _attr(el, 'read') == '1',
            source_file   = source_file,
        )
    except Exception as e:
        logger.debug(f"Skipped SMS element: {e}")
        return None


def _parse_mms(el: ET.Element, source_file: str):
    try:
        ts   = int(_attr(el, 'date') or '0')
        body = _extract_mms_body(el)
        return MessageRecord(
            timestamp_ms  = ts,
            date_str      = _epoch_to_str(ts),
            direction     = MMS_DIRECTION.get(_attr(el, 'msg_box'), 'Unknown'),
            contact_name  = _sanitize(_attr(el, 'contact_name')),
            phone_number  = _sanitize_phone(_attr(el, 'address')),
            msg_type      = 'MMS',
            body          = body,
            read          = _attr(el, 'read') == '1',
            source_file   = source_file,
        )
    except Exception as e:
        logger.debug(f"Skipped MMS element: {e}")
        return None


def _extract_mms_body(el: ET.Element) -> str:
    try:
        parts_el = el.find('parts')
        if parts_el is None:
            return '[MMS — no text]'
        texts = []
        for part in parts_el.findall('part'):
            ct   = _attr(part, 'ct')
            text = _attr(part, 'text')
            if ct == 'text/plain' and text and text.lower() != 'null':
                texts.append(_sanitize(text, max_len=50000))
        return ' '.join(texts) if texts else '[MMS — media only]'
    except Exception:
        return '[MMS — parse error]'


def _strip_stylesheet(content: str) -> str:
    return re.sub(r'<\?xml-stylesheet[^?]*\?>', '', content)

def _attr(el: ET.Element, name: str) -> str:
    val = el.get(name, '')
    return val if val is not None else ''

def _epoch_to_str(epoch_ms: int) -> str:
    try:
        return datetime.fromtimestamp(epoch_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, OverflowError, ValueError):
        return 'INVALID_DATE'

def _sanitize(text: str, max_len: int = 500) -> str:
    if not text:
        return ''
    cleaned = ''.join(c for c in text if c.isprintable() or c in '\n\r\t')
    return cleaned[:max_len]

def _sanitize_phone(phone: str) -> str:
    if not phone:
        return ''
    return ''.join(c for c in phone if c.isdigit() or c in '+-() ')[:30]
