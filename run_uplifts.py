#!/usr/bin/env python3
"""
run_uplifts.py — Nous Loop Solutions
Convenience wrapper for the uplift extractor.

Replaces the old root-level extract_uplifts.py.
This script is a thin shim — all logic is in sentinel/uplifts/extractor.py.

Usage:
    python run_uplifts.py --db sentinel.db
    python run_uplifts.py --db sentinel.db --contact-filter "Mom" --top 20
    python run_uplifts.py --db sentinel.db --sender-only --output my_uplifts.json

All flags from sentinel.uplifts.extractor are supported.
"""

from sentinel.uplifts.extractor import main

if __name__ == '__main__':
    main()
