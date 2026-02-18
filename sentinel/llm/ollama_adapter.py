"""
sentinel/llm/ollama_adapter.py
Ollama backend adapter. Ollama runs locally on Windows and Termux.
Supports any model pulled via `ollama pull <model>`.

INSTALL:
  Windows: https://ollama.com/download
  Termux:  pkg install ollama  (or build from source)

RECOMMENDED MODELS (by VRAM/RAM):
  <4GB RAM:  tinyllama, phi3:mini, qwen2:1.5b
  4-8GB RAM: mistral:7b, llama3:8b, phi3:medium
  8GB+ RAM:  llama3:8b-instruct (best for this task)
"""

import json
import logging
import urllib.request
import urllib.error
from typing import List, Optional

from sentinel.llm.base import LLMAdapter, LLMResponse

logger = logging.getLogger(__name__)


class OllamaAdapter(LLMAdapter):

    def __init__(
        self,
        model:       str   = 'llama3:8b-instruct',
        host:        str   = 'http://localhost:11434',
        timeout_sec: int   = 120,
        temperature: float = 0.1,
    ):
        self.model       = model
        self.host        = host.rstrip('/')
        self.timeout_sec = timeout_sec
        self.temperature = temperature

    # ── AVAILABILITY CHECK ───────────────────────────────────
    def is_available(self) -> bool:
        """Ping Ollama and confirm the configured model is pulled."""
        try:
            url = f"{self.host}/api/tags"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as resp:
                data   = json.loads(resp.read().decode())
                models = [m['name'] for m in data.get('models', [])]

            # Check exact match or prefix match (e.g. "llama3" matches "llama3:8b-instruct")
            available = any(
                m == self.model or m.startswith(self.model.split(':')[0])
                for m in models
            )

            if not available:
                logger.warning(
                    f"Model '{self.model}' not found in Ollama. "
                    f"Available: {models}. "
                    f"Run: ollama pull {self.model}"
                )
            return available

        except urllib.error.URLError:
            logger.warning(
                "Ollama not reachable at " + self.host +
                ". Start Ollama or check if it's running."
            )
            return False
        except Exception as e:
            logger.warning(f"Ollama availability check failed: {e}")
            return False

    # ── ANALYSIS ─────────────────────────────────────────────
    def analyze(
        self,
        body:           str,
        direction:      str,
        contact_name:   str,
        kw_categories:  List[str],
        context_before: List[str],
        context_after:  List[str],
    ) -> Optional[LLMResponse]:

        prompt = self.build_prompt(
            body, direction, contact_name,
            kw_categories, context_before, context_after
        )

        payload = json.dumps({
            'model':  self.model,
            'prompt': prompt,
            'stream': False,
            'options': {
                'temperature': self.temperature,
                'num_predict': 400,
            },
            'format': 'json',   # Ollama JSON mode — forces valid JSON output
        }).encode('utf-8')

        try:
            req = urllib.request.Request(
                f"{self.host}/api/generate",
                data    = payload,
                headers = {'Content-Type': 'application/json'},
                method  = 'POST',
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw  = resp.read().decode('utf-8')
                data = json.loads(raw)

            response_text = data.get('response', '').strip()
            return self._parse_response(response_text)

        except urllib.error.URLError as e:
            logger.error(f"Ollama request failed: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode failed in Ollama response: {e}")
            return None
        except Exception as e:
            logger.error(f"Ollama analyze error: {e}")
            return None

    # ── RESPONSE PARSER ──────────────────────────────────────
    def _parse_response(self, text: str) -> Optional[LLMResponse]:
        """
        Parse Ollama JSON response into LLMResponse.
        Handles models that add markdown fences despite format=json.
        """
        try:
            # Strip markdown fences if present
            clean = text.strip()
            if clean.startswith('```'):
                clean = clean.split('```')[1]
                if clean.startswith('json'):
                    clean = clean[4:]
            clean = clean.strip()

            data = json.loads(clean)

            return LLMResponse(
                confirmed       = bool(data.get('confirmed', False)),
                categories      = [
                    c.upper() for c in data.get('categories', [])
                    if isinstance(c, str)
                ],
                severity        = str(data.get('severity', 'LOW')).upper(),
                flagged_quote   = str(data.get('flagged_quote', ''))[:500],
                context_summary = str(data.get('context_summary', ''))[:1000],
                model_used      = self.model,
                raw_response    = text[:500],
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning(f"Could not parse Ollama response: {e}\nRaw: {text[:200]}")
            return None

    # ── MODEL MANAGEMENT HELPERS ─────────────────────────────
    def list_available_models(self) -> List[str]:
        """Return list of locally available Ollama model names."""
        try:
            req = urllib.request.Request(f"{self.host}/api/tags", method='GET')
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            return [m['name'] for m in data.get('models', [])]
        except Exception:
            return []

    def pull_model(self, model_name: str) -> bool:
        """
        Pull a model from Ollama registry.
        Blocking — use only in setup/init scripts, not during analysis.
        """
        logger.info(f"Pulling model: {model_name} — this may take several minutes...")
        payload = json.dumps({'name': model_name, 'stream': False}).encode()
        try:
            req = urllib.request.Request(
                f"{self.host}/api/pull",
                data    = payload,
                headers = {'Content-Type': 'application/json'},
                method  = 'POST',
            )
            with urllib.request.urlopen(req, timeout=600) as resp:
                data   = json.loads(resp.read().decode())
                status = data.get('status', '')
                logger.info(f"Pull result: {status}")
                return 'success' in status.lower()
        except Exception as e:
            logger.error(f"Model pull failed: {e}")
            return False
