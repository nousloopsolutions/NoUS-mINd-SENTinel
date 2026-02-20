"""
sentinel/report_export.py
Phase 7.3 — Court-admissible export format.

Output: JSON (primary), PDF-ready structured dict (secondary).
Every export includes: report metadata (generated_at, AGENTS.md version, scan params),
data integrity hash (SHA-256 of export content before signing), export format version.
No raw message content — scores, patterns, metadata only.
"""

import hashlib
import json
from typing import Any, Dict, Optional

from sentinel.report import Report, report_to_dict


EXPORT_FORMAT_VERSION = "1.0"


def _build_export_payload(
    report: Report,
    scan_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build export payload (no hash yet). Used for both JSON and dict output."""
    report_metadata = {
        "generated_at": report.generated_at,
        "agents_md_version": report.agents_md_version,
        "scan_parameters": dict(scan_parameters) if scan_parameters else {},
    }
    payload = {
        "export_format_version": EXPORT_FORMAT_VERSION,
        "report_metadata": report_metadata,
        "report": report_to_dict(report),
    }
    return payload


def _content_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 of canonical JSON serialization of payload (no hash field)."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def export_to_json(
    report: Report,
    scan_parameters: Optional[Dict[str, Any]] = None,
    indent: Optional[int] = 2,
) -> str:
    """
    Export report to JSON string (primary format).
    Includes report metadata, integrity hash, and format version.
    """
    payload = _build_export_payload(report, scan_parameters)
    content_hash = _content_hash(payload)
    export_obj = {**payload, "content_hash_sha256": content_hash}
    return json.dumps(export_obj, indent=indent, sort_keys=False)


def export_to_dict(
    report: Report,
    scan_parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Export report to PDF-ready structured dict (secondary).
    Same schema as JSON export; can be passed to PDF generator.
    """
    payload = _build_export_payload(report, scan_parameters)
    content_hash = _content_hash(payload)
    return {**payload, "content_hash_sha256": content_hash}
