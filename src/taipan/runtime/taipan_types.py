"""
Taipan Built-in Types
======================
Wrappers around Python objects that give Taipan its runtime types:
  - PeeList   → growable ordered collection
  - PeeMap    → hash map / dictionary
  - PeeSet    → unordered unique elements
  - PeeTuple  → immutable ordered collection
  - PeeRange  → lazy range for loop iteration
  - PeeFunction → first-class function/closure
  - PeeClass  → class descriptor
  - PeeInstance → object instance
  - PeeAI     → AI assistant object
"""

from __future__ import annotations
from typing import Any, List, Optional, Iterator
import math


# ── PeeList ───────────────────────────────────────────────────────────────────

class PeeList:
    def __init__(self, elements: list = None):
        self._data: list = list(elements) if elements else []

    # Taipan method dispatch
    def pee_method(self, name: str, args: list):
        match name:
            case "append":   self._data.append(args[0]); return None
            case "push":     self._data.append(args[0]); return None
            case "pop":      return self._data.pop() if not args else self._data.pop(int(args[0]))
            case "remove":   self._data.remove(args[0]); return None
            case "insert":   self._data.insert(int(args[0]), args[1]); return None
            case "clear":    self._data.clear(); return None
            case "reverse":  self._data.reverse(); return None
            case "sort":     self._data.sort(key=lambda x: (str(type(x)), x) if not isinstance(x, (int, float)) else x); return None
            case "contains" | "has": return args[0] in self._data
            case "index":    return self._data.index(args[0])
            case "count":    return self._data.count(args[0])
            case "slice":    return PeeList(self._data[int(args[0]):int(args[1])])
            case "join":     sep = args[0] if args else ""; return sep.join(str(x) for x in self._data)
            case "map":      raise NotImplementedError("Higher-order functions via map() built-in")
            case "filter":   raise NotImplementedError("Higher-order functions via filter() built-in")
            case "copy":     return PeeList(self._data[:])
            case "extend":   self._data.extend(args[0]._data if isinstance(args[0], PeeList) else args[0]); return None
            case _: raise AttributeError(f"List has no method '{name}'")

    def pee_attr(self, name: str):
        if name == "length" or name == "len":
            return len(self._data)
        raise AttributeError(f"List has no attribute '{name}'")

    def __len__(self):        return len(self._data)
    def __getitem__(self, i): return self._data[i]
    def __setitem__(self, i, v): self._data[i] = v
    def __iter__(self):       return iter(self._data)
    def __contains__(self, x): return x in self._data
    def __repr__(self):       return f"[{', '.join(pee_repr(x) for x in self._data)}]"
    def __add__(self, other):
        if isinstance(other, PeeList):
            return PeeList(self._data + other._data)
        raise TypeError("Can only concatenate List with List")
    def __eq__(self, other):
        if isinstance(other, PeeList): return self._data == other._data
        return False


# ── PeeMap ────────────────────────────────────────────────────────────────────

class PeeMap:
    def __init__(self, data: dict = None):
        self._data: dict = dict(data) if data else {}

    def pee_method(self, name: str, args: list):
        match name:
            case "get":     return self._data.get(args[0], args[1] if len(args) > 1 else None)
            case "set":     self._data[args[0]] = args[1]; return None
            case "remove" | "delete": del self._data[args[0]]; return None
            case "has" | "contains": return args[0] in self._data
            case "keys":    return PeeList(list(self._data.keys()))
            case "values":  return PeeList(list(self._data.values()))
            case "items":   return PeeList([PeeTuple([k, v]) for k, v in self._data.items()])
            case "clear":   self._data.clear(); return None
            case "update":  self._data.update(args[0]._data if isinstance(args[0], PeeMap) else args[0]); return None
            case "copy":    return PeeMap(self._data.copy())
            case _: raise AttributeError(f"Map has no method '{name}'")

    def pee_attr(self, name: str):
        if name in ("length", "len", "size"):
            return len(self._data)
        raise AttributeError(f"Map has no attribute '{name}'")

    def __getitem__(self, key): return self._data[key]
    def __setitem__(self, key, val): self._data[key] = val
    def __contains__(self, key): return key in self._data
    def __len__(self): return len(self._data)
    def __iter__(self): return iter(self._data)
    def __repr__(self):
        pairs = ", ".join(f"{pee_repr(k)}: {pee_repr(v)}" for k, v in self._data.items())
        return "{" + pairs + "}"
    def __eq__(self, other):
        if isinstance(other, PeeMap): return self._data == other._data
        return False


# ── PeeSet ────────────────────────────────────────────────────────────────────

class PeeSet:
    def __init__(self, elements=None):
        self._data: set = set(elements) if elements else set()

    def pee_method(self, name: str, args: list):
        match name:
            case "add":      self._data.add(args[0]); return None
            case "remove":   self._data.discard(args[0]); return None
            case "has" | "contains": return args[0] in self._data
            case "clear":    self._data.clear(); return None
            case "union":    return PeeSet(self._data | (args[0]._data if isinstance(args[0], PeeSet) else set(args[0])))
            case "intersect":return PeeSet(self._data & (args[0]._data if isinstance(args[0], PeeSet) else set(args[0])))
            case "difference":return PeeSet(self._data - (args[0]._data if isinstance(args[0], PeeSet) else set(args[0])))
            case "toList":   return PeeList(list(self._data))
            case _: raise AttributeError(f"Set has no method '{name}'")

    def pee_attr(self, name: str):
        if name in ("length", "len", "size"):
            return len(self._data)
        raise AttributeError(f"Set has no attribute '{name}'")

    def __len__(self): return len(self._data)
    def __iter__(self): return iter(self._data)
    def __contains__(self, x): return x in self._data
    def __repr__(self): return "{" + ", ".join(pee_repr(x) for x in self._data) + "}"
    def __eq__(self, other):
        if isinstance(other, PeeSet): return self._data == other._data
        return False


# ── PeeTuple ──────────────────────────────────────────────────────────────────

class PeeTuple:
    def __init__(self, elements: list = None):
        self._data: tuple = tuple(elements) if elements else ()

    def pee_method(self, name: str, args: list):
        match name:
            case "index":   return self._data.index(args[0])
            case "count":   return self._data.count(args[0])
            case "contains" | "has": return args[0] in self._data
            case "toList":  return PeeList(list(self._data))
            case _: raise AttributeError(f"Tuple has no method '{name}'")

    def pee_attr(self, name: str):
        if name in ("length", "len", "size"):
            return len(self._data)
        raise AttributeError(f"Tuple has no attribute '{name}'")

    def __len__(self): return len(self._data)
    def __getitem__(self, i): return self._data[i]
    def __iter__(self): return iter(self._data)
    def __contains__(self, x): return x in self._data
    def __repr__(self): return "(" + ", ".join(pee_repr(x) for x in self._data) + ")"
    def __eq__(self, other):
        if isinstance(other, PeeTuple): return self._data == other._data
        if isinstance(other, tuple): return self._data == other
        return False
    def __hash__(self): return hash(self._data)


# ── PeeRange ──────────────────────────────────────────────────────────────────

class PeeRange:
    def __init__(self, start: int, end: int, step: int = 1, inclusive: bool = False):
        self.start     = int(start)
        self.end       = int(end)
        self.step      = int(step) if step else 1
        self.inclusive = inclusive

    def __iter__(self) -> Iterator[int]:
        stop = self.end + 1 if self.inclusive else self.end
        return iter(range(self.start, stop, self.step))

    def __repr__(self):
        return f"{self.start}..{self.end}"

    def __contains__(self, x):
        stop = self.end + 1 if self.inclusive else self.end
        return x in range(self.start, stop, self.step)


# ── PeeFunction ───────────────────────────────────────────────────────────────

class PeeFunction:
    """A Taipan function / closure."""
    def __init__(self, name: str, params, body, closure, is_builtin: bool = False,
                 builtin_fn=None, is_method: bool = False, is_async: bool = False):
        self.name       = name
        self.params     = params       # List[Param]
        self.body       = body         # Block AST node (or None for builtins)
        self.closure    = closure      # Environment at definition time
        self.is_builtin = is_builtin
        self.builtin_fn = builtin_fn   # callable(args) for builtins
        self.is_method  = is_method
        self.is_async   = is_async

    def __repr__(self):
        prefix = "async " if self.is_async else ""
        return f"<{prefix}func {self.name}>"


# ── PeeClass ──────────────────────────────────────────────────────────────────

class PeeClass:
    """A Taipan class descriptor."""
    def __init__(self, name: str, methods: dict, superclass: Optional["PeeClass"] = None):
        self.name       = name
        self.methods    = methods      # str → PeeFunction
        self.superclass = superclass

    def find_method(self, name: str) -> Optional[PeeFunction]:
        if name in self.methods:
            return self.methods[name]
        if self.superclass:
            return self.superclass.find_method(name)
        return None

    def __repr__(self):
        return f"<class {self.name}>"


# ── PeeInstance ───────────────────────────────────────────────────────────────

class PeeInstance:
    """A Taipan object instance."""
    def __init__(self, klass: PeeClass):
        self.klass  = klass
        self.fields: dict[str, Any] = {}

    def get(self, name: str):
        if name in self.fields:
            return self.fields[name]
        method = self.klass.find_method(name)
        if method is not None:
            return BoundMethod(self, method)
        raise AttributeError(f"'{self.klass.name}' object has no attribute '{name}'")

    def set(self, name: str, value: Any):
        self.fields[name] = value

    def __repr__(self):
        return f"<{self.klass.name} instance>"


# ── BoundMethod ───────────────────────────────────────────────────────────────

class BoundMethod:
    """A method bound to an instance (provides 'self')."""
    def __init__(self, instance: PeeInstance, method: PeeFunction):
        self.instance = instance
        self.method   = method

    def __repr__(self):
        return f"<bound method {self.method.name} of {self.instance!r}>"


# ── PeeAI ─────────────────────────────────────────────────────────────────────

class PeeAI:
    """
    AI assistant instance. Uses OpenAI if OPENAI_API_KEY is set,
    otherwise uses a mock response for offline development.
    """
    def __init__(self, name: str = "assistant"):
        self.name   = name
        self._model = "gpt-4o-mini"
        self._client = None
        self._init_client()

    def _init_client(self):
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=api_key)
            except ImportError:
                self._client = None

    def _call_ai(self, prompt: str, system: str = "You are a helpful AI assistant.") -> str:
        if self._client:
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user",   "content": prompt}
                    ],
                    max_tokens=1024,
                )
                return resp.choices[0].message.content.strip()
            except Exception as e:
                return f"[AI Error: {e}]"
        # Offline mock
        return f"[AI Mock Response for: '{prompt[:60]}...']" if len(prompt) > 60 else f"[AI Mock Response for: '{prompt}']"

    def pee_method(self, name: str, args: list):
        match name:
            case "ask":
                prompt = str(args[0]) if args else ""
                return self._call_ai(prompt)
            case "summarize":
                text = str(args[0]) if args else ""
                return self._call_ai(f"Summarize the following text concisely:\n\n{text}",
                                     "You are an expert summarizer.")
            case "generateCode":
                prompt = str(args[0]) if args else ""
                return self._call_ai(f"Generate code for: {prompt}",
                                     "You are an expert programmer. Return only code, no explanation.")
            case "classify":
                text  = str(args[0]) if args else ""
                cats  = args[1] if len(args) > 1 else None
                extra = f" Categories: {cats}" if cats else ""
                return self._call_ai(f"Classify this text into a category:{extra}\n\n{text}",
                                     "You are a text classifier. Return only the category label.")
            case "translate":
                text = str(args[0]) if args else ""
                lang = str(args[1]) if len(args) > 1 else "English"
                return self._call_ai(f"Translate to {lang}:\n\n{text}",
                                     "You are a professional translator.")
            case "sentiment":
                text = str(args[0]) if args else ""
                return self._call_ai(f"Analyze sentiment (positive/negative/neutral):\n\n{text}",
                                     "Return only one word: positive, negative, or neutral.")
            case _:
                raise AttributeError(f"AI assistant has no method '{name}'")

    def __repr__(self):
        return f"<ai {self.name}>"


# ── PeePromise ────────────────────────────────────────────────────────────────

class PeePromise:
    """A wrapper representing an asynchronous computation."""
    def __init__(self, target_fn, *args, **kwargs):
        import threading
        self._result = None
        self._error = None
        self._resolved = False
        self._event = threading.Event()
        
        def run():
            try:
                self._result = target_fn(*args, **kwargs)
            except Exception as e:
                self._error = e
            finally:
                self._resolved = True
                self._event.set()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def wait(self):
        self._event.wait()
        if self._error is not None:
            raise self._error
        return self._result

    def __repr__(self):
        if not self._resolved:
            return "<Promise status=pending>"
        if self._error is not None:
            return f"<Promise status=rejected error={self._error!r}>"
        return f"<Promise status=resolved result={self._result!r}>"


# ── Utility ───────────────────────────────────────────────────────────────────

def pee_repr(value: Any) -> str:
    """Return a Taipan-style string representation of a value."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    if isinstance(value, (PeeList, PeeMap, PeeSet, PeeTuple, PeeRange,
                          PeeFunction, PeeClass, PeeInstance, BoundMethod, PeeAI, PeePromise)):
        return repr(value)
    return repr(value)


def pee_truthy(value: Any) -> bool:
    """Taipan truthiness rules."""
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, (PeeList, PeeMap, PeeSet, PeeTuple)):
        return len(value) > 0
    return True


def pee_str(value: Any) -> str:
    """Convert a Taipan value to its string representation (for show())."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (PeeList, PeeMap, PeeSet, PeeTuple, PeePromise)):
        return repr(value)
    return str(value)
