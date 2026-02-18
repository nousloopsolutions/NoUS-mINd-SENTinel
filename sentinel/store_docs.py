"""
sentinel/store_docs.py
Google Play Store documentation — bundled for standalone app.
Served via API at /store/* endpoints.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

# Project root (parent of sentinel/)
_PKG_DIR = Path(__file__).resolve().parent
_DOCS_DIR = _PKG_DIR.parent / "docs"
_ROOT = _PKG_DIR.parent


def _read_doc(name: str) -> str:
    """Read doc file from docs/ or return empty."""
    path = _DOCS_DIR / name
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


def get_listing() -> Dict[str, Any]:
    """Google Play Store listing — for /store/listing endpoint."""
    return {
        "app_name": "mINd-SENTinel",
        "store_listing_name": "mINd-SENTinel — Intent Analyzer",
        "package_name": "solutions.nousloop.mind.sentinel",
        "category": "Tools",
        "price": "Free",
        "in_app_purchases": False,
        "short_description": "Analyze SMS & calls for intent. 100% on-device. No data leaves your phone.",
        "full_description": _read_doc("PLAY_STORE_LISTING.md") or _listing_fallback(),
        "promotional_text": "Analyze SMS & calls for intent. 100% on-device. No data leaves your phone. Built for neurodivergent advocates and families. Free forever.",
        "whats_new": "Onboarding wizard, voice commands, personalized prompts, Termux/Z Fold 4 support.",
        "contact": {
            "github": "https://github.com/nousloopsolutions/mINd-SENTinel",
            "company": "Nous Loop Solutions, Minnesota",
        },
    }


def _listing_fallback() -> str:
    return """mINd-SENTinel analyzes your SMS and call log backups for intent patterns.

KEY FEATURES
• 100% on-device — No data leaves your phone
• Keyword + AI analysis (Ollama on-device)
• Per-contact risk profiles
• Uplifting message extraction
• Legal documentation support

PRIVACY: Your data stays on your device. We never collect or transmit it.

Built by Nous Loop Solutions. Free forever."""


def get_privacy() -> str:
    """Privacy policy — for /store/privacy endpoint."""
    path = _ROOT / "PRIVACY_POLICY.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return """# Privacy Policy — mINd-SENTinel

Your data stays on your device. We do not collect, transmit, sell, or analyze it. We never will.

All processing runs locally. No external servers. No analytics. No telemetry.

— Nous Loop Solutions"""


def get_data_safety() -> Dict[str, Any]:
    """Data Safety declaration — for /store/data-safety endpoint."""
    return {
        "data_collected": False,
        "data_shared": False,
        "data_transmitted": False,
        "summary": "No data shared with third parties. Data is processed on-device only. No data is transmitted to external servers.",
        "data_types_handled_locally": [
            "Messages (SMS/MMS content)",
            "Call logs (numbers, duration, timestamps)",
            "Contacts (names, numbers)",
            "Files (XML backup files)",
        ],
        "permissions": {
            "READ_EXTERNAL_STORAGE": "Read XML backup files",
            "WRITE_EXTERNAL_STORAGE": "Write SQLite database",
        },
        "third_party_sdks": [],
        "full_declaration": _read_doc("DATA_SAFETY.md") or _data_safety_fallback(),
    }


def _data_safety_fallback() -> str:
    return """# Data Safety — mINd-SENTinel

No data collected. No data shared. No data transmitted.

All processing is on-device. Messages, call logs, contacts are read locally only.
No third-party SDKs. No analytics. No advertising."""


def get_legal() -> Dict[str, Any]:
    """Combined legal docs — for /store/legal endpoint."""
    return {
        "privacy_policy": get_privacy(),
        "data_safety": get_data_safety(),
        "listing": get_listing(),
    }
