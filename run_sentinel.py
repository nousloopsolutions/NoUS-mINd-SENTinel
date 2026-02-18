#!/usr/bin/env python3
"""
run_sentinel.py — Fully automated Sentinel pipeline
Uses sentinel_config.json. Run from project root.

  python run_sentinel.py           # scan + build profiles (uses config)
  python run_sentinel.py --scan    # scan only
  python run_sentinel.py --api     # start API server

Config is created by onboarding or manually. Auto-detects XML dir if not set.
"""

import argparse
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="mINd-SENTinel — automated pipeline")
    parser.add_argument("--scan", action="store_true", help="Run scan only")
    parser.add_argument("--api", action="store_true", help="Start API server")
    parser.add_argument("--profiles", action="store_true", help="Build profiles only (after scan)")
    args = parser.parse_args()

    root = Path(__file__).parent
    sys.path.insert(0, str(root))

    from sentinel.config import ensure_config, auto_detect_xml_dir

    config = ensure_config(root)
    xml_dir = config.get("xml_dir")
    if not xml_dir:
        detected = auto_detect_xml_dir()
        xml_dir = str(detected) if detected else None
    db_path = Path(config.get("db_path", "sentinel.db"))
    if not db_path.is_absolute():
        db_path = root / db_path

    if args.api:
        from sentinel.api import _FASTAPI_AVAILABLE
        if not _FASTAPI_AVAILABLE:
            print("Install: pip install fastapi uvicorn", file=sys.stderr)
            sys.exit(1)
        import uvicorn
        from sentinel.api import _build_app
        app = _build_app(db_path=db_path)
        print(f"Starting API at http://127.0.0.1:8765")
        uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
        return

    if args.scan or (not args.profiles and not args.api):
        if not xml_dir or not Path(xml_dir).exists():
            print("No XML dir. Run onboarding or set xml_dir in sentinel_config.json", file=sys.stderr)
            sys.exit(1)
        from sentinel.api import SentinelAPI
        api = SentinelAPI(db_path=db_path)
        print(f"Scanning {xml_dir}...")
        summary = api.run_scan(Path(xml_dir), keyword_only=config.get("keyword_only_default", False))
        print(f"Done: {summary['messages_parsed']} msgs, {summary['intents_flagged']} flags")

    if args.profiles:
        if not db_path.exists():
            print("No database. Run scan first.", file=sys.stderr)
            sys.exit(1)
        import subprocess
        r = subprocess.run([sys.executable, str(root / "build_profiles.py"), "--db", str(db_path)])
        if r.returncode != 0:
            sys.exit(r.returncode)

if __name__ == "__main__":
    main()
