"""
Taipan AI-Powered Error Explanations
=======================================
When a Taipan error occurs, optionally call an AI (local or remote)
to suggest a fix. This makes Taipan the first language with built-in
AI error diagnosis.

Usage:
    setenv TAIPAN_AI_ERRORS=1  # Enable AI error explanations
    setenv OPENAI_API_KEY=...   # Or use Ollama locally

Integration:
    Import this in cli.py and wrap the error printer.
"""

import os
import json
import urllib.request
from typing import Optional

from taipan.runtime.errors import TaipanError


OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

# ── In-memory cache ───────────────────────────────────────────────────────────
# Keyed by (error_type, line, first_80_chars_of_message).
# Prevents redundant API calls when the same error recurs (e.g. in a REPL loop).
_MAX_CACHE = 128
_cache: dict[str, str] = {}


def _cache_key(error: TaipanError, source_line: str = "") -> str:
    return f"{type(error).__name__}:{getattr(error, 'line', 0)}:{str(error)[:80]}:{source_line[:40]}"


def _call_ollama(prompt: str) -> Optional[str]:
    """Call a local Ollama instance for error explanation."""
    try:
        data = json.dumps({
            "model": os.environ.get("OLLAMA_MODEL", "llama3.2"),
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "").strip()
    except Exception:
        return None


def _call_openai(prompt: str) -> Optional[str]:
    """Call OpenAI API for error explanation."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful programming assistant. Given a Taipan error, suggest the exact fix. Keep it to 1-3 lines."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode())
            return result["choices"][0]["message"]["content"].strip()
    except Exception:
        return None


def _build_prompt(error: TaipanError, source_line: str = "") -> str:
    """Build a prompt for the AI from an error."""
    prompt = f"""Taipan error:
{error}
"""
    if source_line:
        prompt += f"\nSource line: {source_line}\n"
    prompt += "\nWhat is the likely cause and how do I fix it? Keep it short."
    return prompt


def ai_explain(error: TaipanError, source_line: str = "") -> Optional[str]:
    """Get an AI explanation for a Taipan error.

    Returns a cached result if the same error was previously explained.
    Returns None if AI is unavailable or disabled.
    """
    # Check cache first
    key = _cache_key(error, source_line)
    if key in _cache:
        return _cache[key]

    prompt = _build_prompt(error, source_line)

    # Try Ollama first (free, local, privacy-preserving)
    result = _call_ollama(prompt)
    if not result:
        # Fall back to OpenAI
        result = _call_openai(prompt)

    if not result:
        # Fall back to local rule-based suggestions
        err_type = type(error).__name__
        msg = str(error).lower()
        if "divisionbyzero" in err_type.lower() or "division by zero" in msg:
            result = "You are trying to divide a number by zero. Check if the denominator variable is 0 before dividing."
        elif "typeerror" in err_type.lower() or "type mismatch" in msg:
            result = "Type mismatch. Ensure variables have compatible types (e.g., convert numbers to strings using str() before concatenating)."
        elif "nameerror" in err_type.lower() or "not defined" in msg:
            result = "Undefined variable or function. Check for typos or ensure the name is declared using 'let' or 'func'."
        elif "indexerror" in err_type.lower() or "index" in msg:
            result = "Index out of range. Check that the index is non-negative and less than the length of the list/string."
        elif "syntaxerror" in err_type.lower():
            result = "Syntax error. Check for missing brackets, parentheses, or operators around this line."
        else:
            result = f"Suggestion: An error of type '{err_type}' occurred. Check variable values, bindings, and syntax."

    if result:
        # Evict oldest entry if cache is full
        if len(_cache) >= _MAX_CACHE:
            oldest = next(iter(_cache))
            del _cache[oldest]
        _cache[key] = result

    return result


def format_error_with_ai(error: TaipanError, source_line: str = "") -> str:
    """Format an error with optional AI explanation."""
    base = str(error)
    suggestion = ai_explain(error, source_line)
    if suggestion:
        # Wrap suggestion lines neatly inside the box
        lines = suggestion.split("\n")
        body = "\n".join(f"│ {ln}" for ln in lines)
        return f"{base}\n\n┌─ AI Suggestion ─────────────────────────┐\n{body}\n└─────────────────────────────────────────┘"
    return base
