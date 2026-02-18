"""
sentinel/llm/base.py
Abstract base class for all LLM adapters.
To add a new backend: subclass LLMAdapter and implement analyze().
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class LLMResponse:
    confirmed:       bool
    categories:      List[str]
    severity:        str           # HIGH / MEDIUM / LOW
    flagged_quote:   str
    context_summary: str
    model_used:      str
    raw_response:    str = ''      # For debugging — never stored in prod output


class LLMAdapter(ABC):
    """
    All LLM backends implement this interface.
    sentinel calls analyze() and gets back an LLMResponse.
    The caller never knows which backend is running.
    """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Returns True if the backend is reachable and ready.
        Called before analysis starts so sentinel can fail fast
        and fall back to keyword-only mode.
        """
        ...

    @abstractmethod
    def analyze(
        self,
        body:           str,
        direction:      str,
        contact_name:   str,
        kw_categories:  List[str],
        context_before: List[str],
        context_after:  List[str],
    ) -> Optional[LLMResponse]:
        """
        Analyze a single message.
        Returns None on API failure — caller falls back to keyword result.
        Never raises — catch internally and return None.
        """
        ...

    def build_prompt(
        self,
        body:           str,
        direction:      str,
        contact_name:   str,
        kw_categories:  List[str],
        context_before: List[str],
        context_after:  List[str],
    ) -> str:
        """
        Shared prompt builder. All adapters use this unless they
        need a format-specific override (e.g. llama.cpp system tags).
        """
        ctx = ''
        if context_before:
            ctx += 'PRIOR MESSAGES (same contact):\n'
            ctx += '\n'.join(context_before) + '\n\n'

        ctx += f'TARGET MESSAGE ({direction}):\n"{body[:1500]}"\n\n'

        if context_after:
            ctx += 'FOLLOWING MESSAGES (same contact):\n'
            ctx += '\n'.join(context_after) + '\n'

        return (
            "You are a forensic communication analyst. "
            "Analyze the target SMS message for harmful, manipulative, "
            "or legally relevant intent.\n\n"
            f"Contact: {contact_name or 'Unknown'}\n"
            f"Keyword pre-scan flagged: {', '.join(kw_categories)}\n\n"
            f"{ctx}\n"
            "Respond ONLY with a valid JSON object. No markdown, no explanation.\n\n"
            "{\n"
            '  "confirmed": true or false,\n'
            '  "categories": ["INSULT","THREAT","MANIPULATION","CUSTODY","POSITIVE"],\n'
            '  "severity": "HIGH" or "MEDIUM" or "LOW",\n'
            '  "flagged_quote": "most significant 1-2 sentences from the message",\n'
            '  "context_summary": "1-2 sentence plain English summary of intent"\n'
            "}\n\n"
            "CATEGORY DEFINITIONS:\n"
            "- INSULT: Personal attacks, name-calling, degrading language\n"
            "- THREAT: Explicit or implied threats — physical, legal, financial\n"
            "- MANIPULATION: Gaslighting, guilt-tripping, blame-shifting, coercion\n"
            "- CUSTODY: Any reference to children, parenting, custody, visitation, child support\n"
            "- POSITIVE: Genuine affection, apology, support, encouragement\n\n"
            "Set confirmed=false ONLY if the message is clearly benign "
            "and keyword match was a false positive.\n"
            "LEGAL NOTE: This analysis is an inference. "
            "Do not present as a legal conclusion."
        )
