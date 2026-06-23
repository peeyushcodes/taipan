"""
Taipan Standard Library — JSON Module
"""
import json as _json
from taipan.runtime.taipan_types import PeeMap, PeeList, PeeFunction
from taipan.runtime.environment import Environment
from taipan.runtime.errors import TaipanRuntimeError


def _py_to_pee(obj):
    """Convert a Python object to a Taipan type."""
    if isinstance(obj, dict):
        return PeeMap({k: _py_to_pee(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return PeeList([_py_to_pee(x) for x in obj])
    return obj


def _pee_to_py(val):
    """Convert a Taipan type back to a Python object for JSON serialization."""
    if isinstance(val, PeeMap):
        return {k: _pee_to_py(v) for k, v in val._data.items()}
    if isinstance(val, PeeList):
        return [_pee_to_py(x) for x in val._data]
    if isinstance(val, (list, dict)):
        return val
    return val


def get_module() -> PeeMap:
    env = Environment(name="stdlib:json")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    def _parse(a):
        try:
            return _py_to_pee(_json.loads(str(a[0])))
        except _json.JSONDecodeError as e:
            raise TaipanRuntimeError(f"Invalid JSON: {e}")

    def _stringify(a):
        indent = int(a[1]) if len(a) > 1 else None
        try:
            return _json.dumps(_pee_to_py(a[0]), indent=indent, ensure_ascii=False)
        except (TypeError, ValueError) as e:
            raise TaipanRuntimeError(f"JSON serialization error: {e}")

    def _load(a):
        path = str(a[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                return _py_to_pee(_json.load(f))
        except FileNotFoundError:
            raise TaipanRuntimeError(f"File not found: '{path}'")
        except _json.JSONDecodeError as e:
            raise TaipanRuntimeError(f"Invalid JSON in '{path}': {e}")

    def _save(a):
        path    = str(a[0])
        content = a[1]
        indent  = int(a[2]) if len(a) > 2 else 2
        with open(path, "w", encoding="utf-8") as f:
            _json.dump(_pee_to_py(content), f, indent=indent, ensure_ascii=False)
        return None

    data = {
        "parse":     _fn("parse",     _parse),
        "stringify": _fn("stringify", _stringify),
        "load":      _fn("load",      _load),
        "save":      _fn("save",      _save),
    }
    return PeeMap(data)
