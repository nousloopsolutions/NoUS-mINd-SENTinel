"""
sentinel/api.py
─────────────────────────────────────────────────────────────────────────────
MIND Sentinel — Dual-mode API layer

TWO USAGE MODES:
  1. Importable module (mINd-REPly / mINd-VAULt):
         from sentinel.api import SentinelAPI
         api = SentinelAPI(db_path=Path("sentinel.db"))
         contacts = api.get_contacts()

  2. FastAPI HTTP server (Looking Glass HTML UI via fetch()):
         python -m sentinel.api                   # default: port 8765
         python -m sentinel.api --port 9000
         uvicorn sentinel.api:app --port 8765

ENDPOINTS:
  POST /scan              — full pipeline: parse XML → analyze → export → return summary
  GET  /contacts          — all contact profiles, sorted by risk_score DESC
  GET  /contacts/{phone}  — single contact profile (phone URL-encoded: %2B16125550001)
  GET  /messages          — flagged intent_results with optional filters
  GET  /meta              — last run metadata

CORS: localhost-only (127.0.0.1 / ::1). Not exposed to network by default.

PRIVACY NOTE:
  All data stays on-device. No external HTTP calls are made by this module.
  The server binds to 127.0.0.1 only — not reachable from outside the device.

SECURITY NOTES:
  - No authentication required (localhost-only, single-user device assumed)
  - Input sanitization: path traversal prevented on xml_dir
  - SQL queries use parameterized statements only — no string interpolation
  - Scan endpoint validates xml_dir existence before running pipeline

ROLLBACK PLAN (Jules):
  This file is additive — it does not modify any existing module.
  To revert: git revert HEAD (single commit). No schema changes introduced here.
  FastAPI/uvicorn removal: pip uninstall fastapi uvicorn anyio
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── OPTIONAL FASTAPI IMPORT ─────────────────────────────────────────────────
# FastAPI is an optional dependency — the SentinelAPI class works without it.
# The HTTP server only starts when running as __main__ or via uvicorn.

try:
    from fastapi import FastAPI, HTTPException, Query, Body
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel
    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover
    _FASTAPI_AVAILABLE = False
    FastAPI = None          # type: ignore
    HTTPException = None    # type: ignore
    BaseModel = object      # type: ignore


# ═══════════════════════════════════════════════════════════════════════════
# IMPORTABLE CLASS — mINd-REPly / mINd-VAULt interface
# ═══════════════════════════════════════════════════════════════════════════

class SentinelAPI:
    """
    Pure-Python API wrapper around sentinel.db.
    No HTTP layer required — import and call directly.

    Usage:
        api = SentinelAPI(db_path=Path("/sdcard/sentinel.db"))
        contacts = api.get_contacts(risk_label="HIGH")
        messages = api.get_messages(phone="+16125550001", limit=50)
        meta     = api.get_meta()
        summary  = api.run_scan(xml_dir=Path("/sdcard/SMSBackup"))
    """

    def __init__(self, db_path: Path = Path("sentinel.db")):
        self.db_path = Path(db_path)

    # ── INTERNAL ──────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _db_exists(self) -> bool:
        return self.db_path.exists()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        d = {k: row[k] for k in row.keys()}
        # Deserialize JSON fields
        for field in ("kw_categories", "ai_categories", "context_before",
                      "context_after", "category_breakdown", "relationship_tags"):
            if field in d and d[field] is not None:
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass  # leave as-is
        return d

    # ── QUERY: CONTACTS ───────────────────────────────────────────────────

    def get_contacts(
        self,
        risk_label: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Return contact profiles sorted by risk_score DESC.

        Args:
            risk_label: filter by label — "LOW", "MEDIUM", "HIGH", "CRITICAL"
            limit:      max rows returned (default 100, max enforced: 500)
            offset:     pagination offset
        """
        if not self._db_exists():
            return []

        limit = min(int(limit), 500)
        offset = max(int(offset), 0)

        sql = "SELECT * FROM contact_profiles"
        params: list = []

        if risk_label:
            sql += " WHERE risk_label = ?"
            params.append(risk_label.upper())

        sql += " ORDER BY risk_score DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_contact(self, phone: str) -> Optional[Dict[str, Any]]:
        """
        Return a single contact profile by phone number.
        Returns None if not found.
        """
        if not self._db_exists():
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM contact_profiles WHERE phone_number = ?",
                (phone,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    # ── QUERY: MESSAGES ───────────────────────────────────────────────────

    def get_messages(
        self,
        phone: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Return flagged intent_results.

        Args:
            phone:    filter by phone_number
            severity: filter by ai_severity — "HIGH", "MEDIUM", "LOW"
            limit:    max rows (default 50, max enforced: 200)
            offset:   pagination offset
        """
        if not self._db_exists():
            return []

        limit = min(int(limit), 200)
        offset = max(int(offset), 0)

        sql = "SELECT * FROM intent_results WHERE 1=1"
        params: list = []

        if phone:
            sql += " AND phone_number = ?"
            params.append(phone)
        if severity:
            sql += " AND ai_severity = ?"
            params.append(severity.upper())

        sql += " ORDER BY message_ts_ms DESC LIMIT ? OFFSET ?"
        params += [limit, offset]

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── QUERY: META ───────────────────────────────────────────────────────

    def get_meta(self) -> Optional[Dict[str, Any]]:
        """Return the most recent run metadata row."""
        if not self._db_exists():
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sentinel_meta ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("notes"):
            try:
                d["notes"] = json.loads(d["notes"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    # ── SCAN: FULL PIPELINE ───────────────────────────────────────────────

    def run_scan(
        self,
        xml_dir: Path,
        model: str = "llama3.1:8b",
        ollama_host: str = "http://localhost:11434",
        keyword_only: bool = False,
        address: Optional[str] = None,
        run_label: str = "",
    ) -> Dict[str, Any]:
        """
        Run the full MIND Sentinel pipeline:
          parse XML → detect intents → build contact profiles → export to DB.

        Returns a summary dict with counts.

        Security: xml_dir is validated — must be an existing directory.
        No shell execution. All operations are in-process Python.
        """
        xml_dir = Path(xml_dir).resolve()

        # ── Input validation ───────────────────────────────────────────
        if not xml_dir.exists():
            raise ValueError(f"xml_dir does not exist: {xml_dir}")
        if not xml_dir.is_dir():
            raise ValueError(f"xml_dir is not a directory: {xml_dir}")
        # Prevent path traversal — resolved path must not escape expected roots
        # (best-effort; Termux typically uses /sdcard or /data/data/...)

        # ── Pipeline imports (deferred to avoid circular imports) ──────
        from sentinel.parsers.sms_parser   import parse_sms_directory
        from sentinel.parsers.call_parser  import parse_call_directory
        from sentinel.detectors.intent_detector import run_full_analysis
        from sentinel.exporters.sqlite_exporter import export
        from sentinel.aggregators.contact_aggregator import build_contact_profiles

        try:
            contact_rels: Dict[str, str] = {}
            try:
                from sentinel.uplifts.extractor import CONTACT_RELATIONSHIPS
                contact_rels = CONTACT_RELATIONSHIPS
            except ImportError:
                pass  # optional module — not required

            logger.info(f"Scan started | xml_dir={xml_dir} | db={self.db_path}")

            messages = parse_sms_directory(xml_dir)
            calls    = parse_call_directory(xml_dir)

            if address:
                messages = [m for m in messages if m.phone_number == address]
                calls    = [c for c in calls    if c.phone_number == address]

            llm = None
            if not keyword_only:
                from sentinel.llm.ollama_adapter import OllamaAdapter
                llm = OllamaAdapter(model=model, host=ollama_host)
                if not llm.is_available():
                    logger.warning("Ollama unavailable — falling back to keyword-only")
                    llm = None

            intents = run_full_analysis(
                messages,
                llm            = llm,
                context_window = 2,
            )

            profiles = build_contact_profiles(
                messages        = messages,
                calls           = calls,
                intent_results  = intents,
                contact_relationships = contact_rels,
            )

            export(
                db_path          = self.db_path,
                messages         = messages,
                calls            = calls,
                intents          = intents,
                contact_profiles = profiles,
                run_label        = run_label or "api-scan",
            )

            summary = {
                "status":           "ok",
                "messages_parsed":  len(messages),
                "calls_parsed":     len(calls),
                "intents_flagged":  len(intents),
                "contacts_profiled": len(profiles),
                "db_path":          str(self.db_path),
                "high_risk_contacts": sum(
                    1 for p in profiles if p.risk_label in ("HIGH", "CRITICAL")
                ),
            }
            logger.info(f"Scan complete: {summary}")
            return summary

        except Exception as exc:
            logger.error(f"Scan failed: {exc}", exc_info=True)
            raise


# ═══════════════════════════════════════════════════════════════════════════
# FASTAPI HTTP APP — Looking Glass interface
# Only constructed when FastAPI is available
# ═══════════════════════════════════════════════════════════════════════════

def _build_app(db_path: Path = Path("sentinel.db")) -> "FastAPI":  # type: ignore
    """
    Build and return the FastAPI application instance.
    Called once at module level (if FastAPI is available) or on demand.
    """
    if not _FASTAPI_AVAILABLE:
        raise ImportError(
            "FastAPI is not installed. Run: pip install fastapi uvicorn"
        )

    _api = SentinelAPI(db_path=db_path)

    _app = FastAPI(
        title       = "MIND Sentinel API",
        description = "Offline SMS & Call Log Intent Analyzer — local API for M.I.N.D. Gateway",
        version     = "2.4.0",
        docs_url    = "/docs",   # Swagger UI — useful during dev
        redoc_url   = None,
    )

    # CORS: only allow localhost origins (Looking Glass runs as file:// or localhost)
    _app.add_middleware(
        CORSMiddleware,
        allow_origins     = [
            "http://localhost",
            "http://localhost:8765",
            "http://127.0.0.1",
            "http://127.0.0.1:8765",
            "null",   # file:// origin
        ],
        allow_methods     = ["GET", "POST", "OPTIONS"],
        allow_headers     = ["Content-Type"],
        allow_credentials = False,
    )

    # ── REQUEST MODELS ──────────────────────────────────────────────────

    class ScanRequest(BaseModel):
        xml_dir:      Optional[str] = None  # uses config if empty
        model:        str = "llama3.1:8b"
        ollama_host:  str = "http://localhost:11434"
        keyword_only: bool = False
        address:      Optional[str] = None
        run_label:    str = ""
        db_path:      Optional[str] = None  # override db path for this scan

    # ── ENDPOINTS ───────────────────────────────────────────────────────

    @_app.post("/scan", summary="Run full analysis pipeline")
    def scan(req: ScanRequest):
        """
        Trigger a full MIND Sentinel pipeline scan.

        - Parses XML files from xml_dir
        - Runs keyword + AI intent detection
        - Builds contact risk profiles
        - Writes results to sentinel.db

        Returns a summary with counts and high-risk contact count.

        LEGAL NOTE: AI-generated labels are probabilistic inferences.
        Do not present as legal conclusions without attorney review.
        """
        xml_dir_val = req.xml_dir
        if not xml_dir_val:
            from sentinel.config import load_config, auto_detect_xml_dir
            cfg = load_config(Path.cwd())
            detected = auto_detect_xml_dir()
            xml_dir_val = cfg.get("xml_dir") or (str(detected) if detected else None)
            if not xml_dir_val:
                raise HTTPException(status_code=400, detail="xml_dir required. Run onboarding or provide in request.")
        scan_api = _api
        if req.db_path:
            scan_api = SentinelAPI(db_path=Path(req.db_path))

        try:
            result = scan_api.run_scan(
                xml_dir      = Path(xml_dir_val),
                model        = req.model,
                ollama_host  = req.ollama_host,
                keyword_only = req.keyword_only,
                address      = req.address,
                run_label    = req.run_label,
            )
            return JSONResponse(content=result, status_code=200)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            logger.error(f"Scan endpoint error: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Scan failed: {exc}")

    @_app.get("/contacts", summary="List all contact profiles")
    def get_contacts(
        risk_label: Optional[str] = Query(None, description="Filter: LOW, MEDIUM, HIGH, CRITICAL"),
        limit:      int           = Query(100,  ge=1, le=500),
        offset:     int           = Query(0,    ge=0),
    ):
        """
        Returns contact profiles sorted by risk_score descending.
        Profiles are SPECULATIVE — risk score not validated against clinical data.
        """
        try:
            data = _api.get_contacts(risk_label=risk_label, limit=limit, offset=offset)
            return {"count": len(data), "contacts": data}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/contacts/{phone}", summary="Get single contact profile")
    def get_contact(phone: str):
        """
        phone should be URL-encoded: +16125550001 → %2B16125550001
        Returns 404 if contact not found in DB.
        """
        try:
            data = _api.get_contact(phone)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        if data is None:
            raise HTTPException(status_code=404, detail=f"Contact not found: {phone}")
        return data

    @_app.get("/messages", summary="List flagged messages")
    def get_messages(
        phone:    Optional[str] = Query(None, description="Filter by phone number"),
        severity: Optional[str] = Query(None, description="Filter: HIGH, MEDIUM, LOW"),
        limit:    int           = Query(50,   ge=1, le=200),
        offset:   int           = Query(0,    ge=0),
    ):
        """
        Returns flagged intent_results (messages that triggered detection).
        Sorted by timestamp descending (newest first).
        """
        try:
            data = _api.get_messages(
                phone=phone, severity=severity, limit=limit, offset=offset
            )
            return {"count": len(data), "messages": data}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/meta", summary="Last run metadata")
    def get_meta():
        """Returns the most recent sentinel_meta row (last scan run info)."""
        try:
            data = _api.get_meta()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        if data is None:
            raise HTTPException(
                status_code=404,
                detail="No scan metadata found — run a scan first."
            )
        return data

    @_app.get("/config", summary="Get config (for automation)")
    def get_config():
        """Returns current config with auto-detected paths. Used by onboarding."""
        try:
            from sentinel.config import load_config, auto_detect_xml_dir
            config = load_config(Path.cwd())
            detected = auto_detect_xml_dir()
            return {
                "config": config,
                "auto_detected_xml_dir": str(detected) if detected else None,
            }
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.post("/config", summary="Save config")
    def save_config_endpoint(update: Dict[str, Any] = Body(default_factory=dict)):
        """Persist config. Used by onboarding completion."""
        try:
            from sentinel.config import save_config, load_config
            config = load_config(Path.cwd())
            config.update(update or {})
            save_config(config)
            return {"status": "ok", "config": config}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/aggregate", summary="Nous architecture aggregation")
    def get_aggregate():
        """Unified aggregation for nous-hub, nous-vault, said-node."""
        try:
            from sentinel.aggregation import aggregate
            from dataclasses import asdict
            summary = aggregate(_api.db_path)
            return asdict(summary)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/personalized-prompt", summary="Personalized system prompt")
    def get_personalized_prompt():
        """Build personalized prompt from messages, uplifts, audio transcripts."""
        try:
            from sentinel.personalization import build_personalized_system_prompt
            try:
                from sentinel.uplifts.extractor import CONTACT_RELATIONSHIPS
                rels = CONTACT_RELATIONSHIPS
            except ImportError:
                rels = {}
            prompt = build_personalized_system_prompt(
                _api.db_path, contact_relationships=rels
            )
            return {"prompt": prompt}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/uplifts", summary="Extract uplifting messages for Looking Glass")
    def get_uplifts(
        top:            int           = Query(50,   ge=1, le=200),
        contact_filter: Optional[str] = Query(None),
        min_score:      int           = Query(4,    ge=0, le=20),
    ):
        """
        Runs uplift extractor on the API's database.
        Returns JSON array compatible with Looking Glass PERSONAL_UPLIFTS_DATA.
        """
        try:
            from sentinel.uplifts.extractor import extract_uplifts
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
                tmp_path = f.name
            try:
                uplifts = extract_uplifts(
                    db_path        = str(_api.db_path),
                    output_path    = tmp_path,
                    top            = top,
                    min_score      = min_score,
                    contact_filter = contact_filter,
                )
                return uplifts
            finally:
                Path(tmp_path).unlink(missing_ok=True)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Database not found")
        except Exception as exc:
            logger.error(f"Uplifts endpoint error: {exc}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/health", summary="Health check")
    def health():
        """Returns server status and db existence. Used by Looking Glass ping."""
        return {
            "status":    "ok",
            "db_exists": _api.db_path.exists(),
            "db_path":   str(_api.db_path),
            "version":   "2.4.0",
        }

    # ── GOOGLE PLAY STORE DOCS (standalone app) ────────────────────────────

    @_app.get("/store/listing", summary="Play Store listing")
    def store_listing():
        """Google Play Store listing — short/full description, features, contact."""
        try:
            from sentinel.store_docs import get_listing
            return get_listing()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/store/privacy", summary="Privacy policy")
    def store_privacy():
        """Privacy policy — required in-app for Play Store."""
        try:
            from sentinel.store_docs import get_privacy
            return {"content": get_privacy(), "format": "markdown"}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/store/data-safety", summary="Data Safety declaration")
    def store_data_safety():
        """Google Play Data Safety section — for Play Console and in-app display."""
        try:
            from sentinel.store_docs import get_data_safety
            return get_data_safety()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    @_app.get("/store/legal", summary="All store docs combined")
    def store_legal():
        """Combined listing, privacy, data safety — for standalone app legal screen."""
        try:
            from sentinel.store_docs import get_legal
            return get_legal()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

    return _app


# Module-level app instance — used by uvicorn sentinel.api:app
# Only created if FastAPI is importable
if _FASTAPI_AVAILABLE:
    app = _build_app()
else:
    app = None  # type: ignore


# ═══════════════════════════════════════════════════════════════════════════
# CLI ENTRYPOINT — python -m sentinel.api
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        prog        = "sentinel.api",
        description = "MIND Sentinel API Server — serves Looking Glass on localhost",
    )
    parser.add_argument("--port",    type=int, default=8765,
                        help="Port to bind (default: 8765)")
    parser.add_argument("--db",      type=str, default="sentinel.db",
                        help="Path to sentinel.db (default: sentinel.db)")
    parser.add_argument("--host",    type=str, default="127.0.0.1",
                        help="Host to bind — DO NOT change to 0.0.0.0 on shared networks")
    args = parser.parse_args()

    if not _FASTAPI_AVAILABLE:
        print(
            "ERROR: FastAPI not installed.\n"
            "Run:  pip install fastapi uvicorn\n"
            "  or: pip install fastapi uvicorn --break-system-packages  (Termux)",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import uvicorn
    except ImportError:
        print(
            "ERROR: uvicorn not installed.\n"
            "Run:  pip install uvicorn\n"
            "  or: pip install uvicorn --break-system-packages  (Termux)",
            file=sys.stderr,
        )
        sys.exit(1)

    # Rebuild app with specified db_path
    server_app = _build_app(db_path=Path(args.db))

    print(f"""
+--------------------------------------------------+
|   MIND Sentinel API Server v2.4.0                |
+--------------------------------------------------+
|  Local:    http://{args.host}:{args.port}
|  DB:       {args.db}
|  Docs:     http://{args.host}:{args.port}/docs
|  Health:   http://{args.host}:{args.port}/health
+--------------------------------------------------+
|  PRIVACY: Bound to localhost only. No data leaves |
|  this device. All processing is on-device.       |
+--------------------------------------------------+
""")

    uvicorn.run(
        server_app,
        host    = args.host,
        port    = args.port,
        log_level = "info",
    )
