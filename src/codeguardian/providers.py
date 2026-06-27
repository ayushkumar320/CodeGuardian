"""Model provider router: Groq -> Hugging Face -> deterministic.

The deterministic path must always work with zero keys (strict rule #3). LLM
output only ever *rephrases* the summary; it can never create a finding or change
the score (strict rule #2). Any provider failure falls through to the next.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

import requests

from .models import Provider, Report
from .security import wrap_untrusted

_TIMEOUT = 20
_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = "llama-3.1-8b-instant"
_HF_URL = "https://api-inference.huggingface.co/models/{model}"
_HF_MODEL = "mistralai/Mistral-7B-Instruct-v0.2"


@dataclass
class SummaryResult:
    text: str
    provider: Provider


def select_provider(env: Optional[dict] = None) -> Provider:
    env = env or os.environ
    if env.get("GROQ_API_KEY"):
        return Provider.groq
    if env.get("HF_TOKEN"):
        return Provider.huggingface
    return Provider.deterministic


def summarize(report: Report, env: Optional[dict] = None) -> SummaryResult:
    """Produce a one-paragraph plain-language summary of the risk.

    Always returns a valid result; on any model error, returns the deterministic
    template. The structured report is the source of truth either way.
    """
    env = env or os.environ
    provider = select_provider(env)
    prompt = _build_prompt(report)

    if provider == Provider.groq:
        text = validate_summary(_try_groq(prompt, env))
        if text:
            return SummaryResult(text, Provider.groq)
        provider = Provider.huggingface if env.get("HF_TOKEN") else Provider.deterministic

    if provider == Provider.huggingface:
        text = validate_summary(_try_hf(prompt, env))
        if text:
            return SummaryResult(text, Provider.huggingface)

    return SummaryResult(deterministic_summary(report), Provider.deterministic)


def validate_summary(raw: Optional[str]) -> Optional[str]:
    """Validate model output against the expected schema: a JSON object with a
    non-empty string ``summary``. Any deviation returns None so the caller falls
    through to the next provider / deterministic template (strict rule: validate
    every model response; invalid output never reaches the user).
    """
    if not raw:
        return None
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        return None
    try:
        obj = json.loads(raw[start : end + 1])
    except ValueError:
        return None
    summary = obj.get("summary") if isinstance(obj, dict) else None
    if isinstance(summary, str) and summary.strip():
        return summary.strip()
    return None


def deterministic_summary(report: Report) -> str:
    active = report.active_findings()
    if not active:
        return "No risk evidence found. This change looks safe to merge."
    areas = ", ".join(report.affected_areas) or "the changed files"
    top = active[0]
    return (
        f"Risk {report.risk.score}/10 ({report.risk.level.value}). "
        f"Affects {areas}. Top concern: {top.title}. "
        f"{len(active)} finding(s) total."
    )


def _build_prompt(report: Report) -> str:
    # Only structured, already-redacted facts go to the model. No raw source.
    facts = {
        "score": report.risk.score,
        "level": report.risk.level.value,
        "affected_areas": report.affected_areas,
        "findings": [
            {"title": f.title, "severity": f.severity.value, "action": f.recommended_actions[:1]}
            for f in report.active_findings()
        ],
    }
    system = (
        "You are CodeGuardian. Summarize this PR merge risk in 2-3 sentences for a "
        "developer. Use ONLY the structured facts provided. Do not invent findings. "
        'Respond with a JSON object of the exact form {"summary": "..."} and nothing else.'
    )
    return f"{system}\n\n{wrap_untrusted(json.dumps(facts, indent=2))}"


def _try_groq(prompt: str, env: dict) -> Optional[str]:
    try:
        resp = requests.post(
            _GROQ_URL,
            headers={"Authorization": f"Bearer {env['GROQ_API_KEY']}"},
            json={
                "model": _GROQ_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "max_tokens": 200,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, ValueError):
        return None


def _try_hf(prompt: str, env: dict) -> Optional[str]:
    try:
        resp = requests.post(
            _HF_URL.format(model=_HF_MODEL),
            headers={"Authorization": f"Bearer {env['HF_TOKEN']}"},
            json={"inputs": prompt, "parameters": {"max_new_tokens": 200, "temperature": 0.2}},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data and "generated_text" in data[0]:
            return data[0]["generated_text"].strip()
        return None
    except (requests.RequestException, KeyError, ValueError, IndexError):
        return None
