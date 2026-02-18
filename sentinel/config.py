"""
sentinel/config.py
Automated config with auto-detection. Persists to sentinel_config.json.
Enables fully automated, user-friendly operation.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "xml_dir": None,
    "db_path": "sentinel.db",
    "model": "llama3.1:8b",
    "ollama_host": "http://localhost:11434",
    "keyword_only_default": False,
    "auto_scan_on_start": False,
    "onboarding_complete": False,
    "user_name": "",
    "contact_relationships": {},
}

# Common backup locations to auto-detect
AUTO_DETECT_PATHS = [
    Path(r"G:\My Drive\Chat Message Backup"),
    Path(r"C:\Users") / "{user}" / "Documents" / "Chat Message Backup",
    Path.home() / "Chat Message Backup",
    Path.home() / "SMSBackup",
    Path("/sdcard/SMSBackup"),
    Path("/sdcard/Download/SMSBackup"),
]


def _config_path(project_root: Optional[Path] = None) -> Path:
    root = project_root or Path.cwd()
    return root / "sentinel_config.json"


def load_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load config from sentinel_config.json. Returns defaults if missing."""
    path = _config_path(project_root)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return {**DEFAULT_CONFIG, **data}
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Config load failed: {e}")
    return dict(DEFAULT_CONFIG)


def save_config(config: Dict[str, Any], project_root: Optional[Path] = None) -> Path:
    """Persist config to sentinel_config.json."""
    path = _config_path(project_root)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return path


def auto_detect_xml_dir() -> Optional[Path]:
    """Scan common paths for sms-*.xml files. Returns first match or None."""
    import os
    paths_to_check = []
    for p in AUTO_DETECT_PATHS:
        try:
            expanded = p
            if "{user}" in str(p):
                expanded = Path(str(p).format(user=os.environ.get("USERNAME", "user")))
            if expanded.exists() and expanded.is_dir():
                paths_to_check.append(expanded)
        except (KeyError, TypeError):
            continue
    for d in paths_to_check:
        if list(d.glob("sms-*.xml")):
            return d
    return None


def ensure_config(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load or create config. Auto-detect xml_dir if not set.
    Returns merged config.
    """
    config = load_config(project_root)
    if not config.get("xml_dir") and config.get("onboarding_complete") is False:
        detected = auto_detect_xml_dir()
        if detected:
            config["xml_dir"] = str(detected)
            logger.info(f"Auto-detected XML dir: {detected}")
    return config
