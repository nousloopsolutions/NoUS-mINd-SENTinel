"""
sentinel/cli.py
Command-line interface for MIND Sentinel.
Works on Windows, Linux, Mac, and Android Termux.

USAGE:
  python -m sentinel.cli --xml-dir ./backups --output ./sentinel.db
  python -m sentinel.cli --xml-dir ./backups --output ./sentinel.db --model llama3:8b-instruct
  python -m sentinel.cli --xml-dir ./backups --output ./sentinel.db --keyword-only
  python -m sentinel.cli --list-models

EXAMPLES:
  # Full pipeline with AI
  python -m sentinel.cli --xml-dir "C:/Drive/Chat Message Backup" --output sentinel.db

  # Keyword-only (no Ollama required)
  python -m sentinel.cli --xml-dir ./backups --output sentinel.db --keyword-only

  # Termux
  python -m sentinel.cli --xml-dir /sdcard/SMSBackup --output /sdcard/sentinel.db
"""

import argparse
import logging
import sys
import time
from pathlib import Path

from sentinel.parsers.sms_parser  import parse_sms_directory
from sentinel.parsers.call_parser import parse_call_directory
from sentinel.detectors.intent_detector import run_full_analysis
from sentinel.exporters.sqlite_exporter import export

logger = logging.getLogger(__name__)

# ANSI colors — disabled automatically on Windows if not supported
GREEN  = '\033[92m'
YELLOW = '\033[93m'
RED    = '\033[91m'
CYAN   = '\033[96m'
RESET  = '\033[0m'
BOLD   = '\033[1m'


def main():
    parser = argparse.ArgumentParser(
        prog        = 'sentinel',
        description = 'MIND Sentinel — Offline SMS & Call Log Intent Analyzer',
        formatter_class = argparse.RawDescriptionHelpFormatter,
        epilog = """
LEGAL NOTICE:
  AI-generated intent labels are probabilistic inferences.
  Do not present as legal conclusions without attorney review.
  All processing is local — no data leaves your device.
        """
    )

    parser.add_argument(
        '--xml-dir', '-d',
        required = True,
        type     = Path,
        help     = 'Directory containing sms-*.xml and calls-*.xml files',
    )
    parser.add_argument(
        '--output', '-o',
        default = Path('sentinel.db'),
        type    = Path,
        help    = 'Output SQLite database path (default: sentinel.db)',
    )
    parser.add_argument(
        '--model', '-m',
        default = 'llama3:8b-instruct',
        help    = 'Ollama model name (default: llama3:8b-instruct)',
    )
    parser.add_argument(
        '--ollama-host',
        default = 'http://localhost:11434',
        help    = 'Ollama host URL (default: http://localhost:11434)',
    )
    parser.add_argument(
        '--keyword-only', '-k',
        action  = 'store_true',
        help    = 'Skip AI analysis — run keyword detection only (no Ollama required)',
    )
    parser.add_argument(
        '--context-window',
        type    = int,
        default = 2,
        help    = 'Messages before/after for context (default: 2)',
    )
    parser.add_argument(
        '--list-models',
        action  = 'store_true',
        help    = 'List locally available Ollama models and exit',
    )
    parser.add_argument(
        '--run-label',
        default = '',
        help    = 'Label for this run (stored in sentinel_meta table)',
    )
    parser.add_argument(
        '--verbose', '-v',
        action  = 'store_true',
        help    = 'Enable debug logging',
    )
    parser.add_argument(
        '--sms-only',
        action  = 'store_true',
        help    = 'Parse SMS/MMS files only — skip call logs',
    )
    parser.add_argument(
        '--calls-only',
        action  = 'store_true',
        help    = 'Parse call log files only — skip SMS',
    )
    parser.add_argument(
        '--extract-uplifts', '-u',
        action  = 'store_true',
        help    = 'After analysis, extract uplifting messages → uplifts.json',
    )
    parser.add_argument(
        '--uplifts-output',
        default = 'uplifts.json',
        type    = Path,
        help    = 'Output path for uplifts JSON (default: uplifts.json)',
    )
    parser.add_argument(
        '--uplifts-top',
        type    = int,
        default = 50,
        help    = 'Max uplifts to export (default: 50)',
    )

    args = parser.parse_args()

    # ── LOGGING SETUP ────────────────────────────────────────
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level   = log_level,
        format  = '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt = '%H:%M:%S',
    )

    # ── LIST MODELS ──────────────────────────────────────────
    if args.list_models:
        from sentinel.llm.ollama_adapter import OllamaAdapter
        adapter = OllamaAdapter(host=args.ollama_host)
        models  = adapter.list_available_models()
        if models:
            _print(f"\n{BOLD}Available Ollama models:{RESET}")
            for m in models:
                _print(f"  • {m}")
        else:
            _print(f"{YELLOW}No models found. Is Ollama running?{RESET}")
        sys.exit(0)

    # ── VALIDATE INPUT DIR ───────────────────────────────────
    xml_dir = args.xml_dir
    if not xml_dir.exists():
        _print(f"{RED}Error: Directory not found: {xml_dir}{RESET}")
        sys.exit(1)

    _banner()
    _print(f"Source directory : {CYAN}{xml_dir}{RESET}")
    _print(f"Output database  : {CYAN}{args.output}{RESET}")
    _print(f"Detection mode   : {CYAN}{'Keyword-only' if args.keyword_only else 'Keyword + Ollama AI'}{RESET}")
    if not args.keyword_only:
        _print(f"Model            : {CYAN}{args.model}{RESET}")
    _print("")

    # ── PARSE ────────────────────────────────────────────────
    messages = []
    calls    = []

    if not args.calls_only:
        _step("Parsing SMS/MMS files...")
        t0       = time.time()
        messages = parse_sms_directory(xml_dir)
        _ok(f"{len(messages)} messages parsed in {_elapsed(t0)}")

    if not args.sms_only:
        _step("Parsing call log files...")
        t0    = time.time()
        calls = parse_call_directory(xml_dir)
        _ok(f"{len(calls)} call records parsed in {_elapsed(t0)}")

    if not messages and not calls:
        _print(f"\n{YELLOW}No XML files found in {xml_dir}{RESET}")
        _print("Check that files are named sms-*.xml and calls-*.xml")
        sys.exit(1)

    # ── INTENT ANALYSIS ──────────────────────────────────────
    llm     = None
    intents = []

    if messages:
        _step("Running intent analysis...")

        if not args.keyword_only:
            from sentinel.llm.ollama_adapter import OllamaAdapter
            llm = OllamaAdapter(model=args.model, host=args.ollama_host)

            if not llm.is_available():
                _print(
                    f"\n{YELLOW}⚠ Ollama unavailable — falling back to keyword-only mode.{RESET}\n"
                    f"  To enable AI: start Ollama, then run:\n"
                    f"  ollama pull {args.model}\n"
                )
                llm = None

        t0 = time.time()

        def progress(current, total, msg):
            pct = int((current / total) * 40)
            bar = '█' * pct + '░' * (40 - pct)
            sys.stdout.write(
                f"\r  [{bar}] {current}/{total} — {msg[:40]:<40}"
            )
            sys.stdout.flush()

        intents = run_full_analysis(
            messages       = messages,
            llm            = llm,
            context_window = args.context_window,
            progress_cb    = progress,
        )

        sys.stdout.write('\n')
        mode = 'AI-confirmed' if llm else 'keyword'
        _ok(
            f"{len(intents)} {mode} flags in {_elapsed(t0)}"
        )

    # ── EXPORT ───────────────────────────────────────────────
    _step("Writing SQLite database...")
    t0 = time.time()
    export(
        db_path   = args.output,
        messages  = messages,
        calls     = calls,
        intents   = intents,
        run_label = args.run_label or str(xml_dir),
    )
    _ok(f"Database written in {_elapsed(t0)}")

    # ── SUMMARY ──────────────────────────────────────────────
    _print(f"\n{BOLD}{GREEN}✓ Complete{RESET}")
    _print(f"  Messages   : {len(messages):,}")
    _print(f"  Calls      : {len(calls):,}")
    _print(f"  Flags      : {len(intents):,}")
    _print(f"  Database   : {args.output.resolve()}")

    # Severity breakdown
    if intents:
        high   = sum(1 for r in intents if r.ai_severity == 'HIGH')
        medium = sum(1 for r in intents if r.ai_severity == 'MEDIUM')
        low    = sum(1 for r in intents if r.ai_severity == 'LOW')
        _print(f"\n  Severity breakdown:")
        _print(f"    🔴 HIGH   : {high}")
        _print(f"    ⚠  MEDIUM : {medium}")
        _print(f"    🟡 LOW    : {low}")

    _print(f"\n{YELLOW}⚖ LEGAL NOTE: AI labels are probabilistic inferences only.{RESET}")
    _print(f"  Consult your attorney before using in any legal proceeding.\n")

    # ── UPLIFT EXTRACTION ────────────────────────────────────
    if args.extract_uplifts:
        _step("Extracting uplifts for The Looking Glass...")
        try:
            from sentinel.uplifts.extractor import extract_uplifts
            uplifts = extract_uplifts(
                db_path     = str(args.output),
                output_path = str(args.uplifts_output),
                top         = args.uplifts_top,
            )
            _ok(f"{len(uplifts)} uplifts → {args.uplifts_output}")
            _print(f"\n  Open looking_glass/index.html and paste your uplifts.json path.")
            _print(f"  Or embed it directly in PERSONAL_UPLIFTS_DATA in the HTML.")
        except Exception as e:
            _print(f"  {YELLOW}⚠ Uplift extraction failed: {e}{RESET}")


# ── PRINT HELPERS ────────────────────────────────────────────

def _banner():
    _print(f"""
{BOLD}{CYAN}
  ███╗   ███╗██╗███╗   ██╗██████╗
  ████╗ ████║██║████╗  ██║██╔══██╗
  ██╔████╔██║██║██╔██╗ ██║██║  ██║
  ██║╚██╔╝██║██║██║╚██╗██║██║  ██║
  ██║ ╚═╝ ██║██║██║ ╚████║██████╔╝
  ╚═╝     ╚═╝╚═╝╚═╝  ╚═══╝╚═════╝
  SENTINEL — Nous Loop Solutions
  Offline Intent Analyzer | M.I.N.D. Archive Pipeline
{RESET}""")

def _step(msg):  _print(f"  {CYAN}→{RESET} {msg}")
def _ok(msg):    _print(f"  {GREEN}✓{RESET} {msg}")
def _print(msg): print(msg)

def _elapsed(t0: float) -> str:
    s = time.time() - t0
    return f"{s:.1f}s" if s < 60 else f"{int(s//60)}m {int(s%60)}s"


if __name__ == '__main__':
    main()

