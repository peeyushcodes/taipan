"""
Taipan Standard Library — AI Module
Provides AI-powered functions: ask, summarize, generateCode, classify, translate, etc.
Uses OpenAI API when OPENAI_API_KEY is set; Ollama when available; falls back to mock.
"""
import os as _os
import json
import urllib.request
from taipan.runtime.taipan_types import PeeMap, PeeFunction, PeeAI
from taipan.runtime.environment import Environment


def _call_ollama(prompt: str, system: str = "") -> str:
    """Call local Ollama instance."""
    host = _os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    try:
        data = json.dumps({
            "model": _os.environ.get("OLLAMA_MODEL", "llama3.2"),
            "prompt": prompt,
            "system": system,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{host}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "[no response]").strip()
    except Exception:
        return None


def _call_openai(prompt: str) -> str:
    """Call OpenAI API."""
    api_key = _os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        data = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
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


def _ai_call(prompt: str) -> str:
    """Route to Ollama -> OpenAI -> Mock."""
    # Try Ollama first (local, free, private)
    result = _call_ollama(prompt)
    if result:
        return result
    # Try OpenAI
    result = _call_openai(prompt)
    if result:
        return result
    # Mock fallback
    return f"[AI Offline] Mock response for: {prompt[:50]}..."


def get_module() -> PeeMap:
    env = Environment(name="stdlib:ai")
    _ai = PeeAI(name="module")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    data = {
        "ask":          _fn("ask",          lambda a: _ai.pee_method("ask", a)),
        "summarize":    _fn("summarize",    lambda a: _ai.pee_method("summarize", a)),
        "generateCode": _fn("generateCode", lambda a: _ai.pee_method("generateCode", a)),
        "classify":     _fn("classify",     lambda a: _ai.pee_method("classify", a)),
        "translate":    _fn("translate",    lambda a: _ai.pee_method("translate", a)),
        "sentiment":    _fn("sentiment",    lambda a: _ai.pee_method("sentiment", a)),
        "isAvailable":  _fn("isAvailable",  lambda a: bool(_os.environ.get("OPENAI_API_KEY") or _call_ollama("ping"))),
        "setModel":     _fn("setModel",     lambda a: setattr(_ai, "_model", str(a[0])) or None),
        "getModel":     _fn("getModel",     lambda a: _ai._model),
    }
    return PeeMap(data)
