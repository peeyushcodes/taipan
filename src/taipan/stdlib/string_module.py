"""
Taipan Standard Library — String Module
"""
import re as _re
from taipan.runtime.taipan_types import PeeMap, PeeList, PeeFunction
from taipan.runtime.environment import Environment


def get_module() -> PeeMap:
    env = Environment(name="stdlib:string")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    data = {
        "upper":      _fn("upper",      lambda a: str(a[0]).upper()),
        "lower":      _fn("lower",      lambda a: str(a[0]).lower()),
        "title":      _fn("title",      lambda a: str(a[0]).title()),
        "capitalize": _fn("capitalize", lambda a: str(a[0]).capitalize()),
        "strip":      _fn("strip",      lambda a: str(a[0]).strip(str(a[1]) if len(a)>1 else None)),
        "lstrip":     _fn("lstrip",     lambda a: str(a[0]).lstrip()),
        "rstrip":     _fn("rstrip",     lambda a: str(a[0]).rstrip()),
        "split":      _fn("split",      lambda a: PeeList(str(a[0]).split(str(a[1]) if len(a)>1 else None))),
        "join":       _fn("join",       lambda a: str(a[0]).join(str(x) for x in (a[1]._data if hasattr(a[1], '_data') else a[1]))),
        "replace":    _fn("replace",    lambda a: str(a[0]).replace(str(a[1]), str(a[2]))),
        "contains":   _fn("contains",   lambda a: str(a[1]) in str(a[0])),
        "startsWith": _fn("startsWith", lambda a: str(a[0]).startswith(str(a[1]))),
        "endsWith":   _fn("endsWith",   lambda a: str(a[0]).endswith(str(a[1]))),
        "indexOf":    _fn("indexOf",    lambda a: str(a[0]).find(str(a[1]))),
        "substring":  _fn("substring",  lambda a: str(a[0])[int(a[1]):int(a[2])]),
        "repeat":     _fn("repeat",     lambda a: str(a[0]) * int(a[1])),
        "reverse":    _fn("reverse",    lambda a: str(a[0])[::-1]),
        "padLeft":    _fn("padLeft",    lambda a: str(a[0]).rjust(int(a[1]), str(a[2]) if len(a)>2 else " ")),
        "padRight":   _fn("padRight",   lambda a: str(a[0]).ljust(int(a[1]), str(a[2]) if len(a)>2 else " ")),
        "trim":       _fn("trim",       lambda a: str(a[0]).strip()),
        "length":     _fn("length",     lambda a: len(str(a[0]))),
        "isEmpty":    _fn("isEmpty",    lambda a: len(str(a[0])) == 0),
        "isDigit":    _fn("isDigit",    lambda a: str(a[0]).isdigit()),
        "isAlpha":    _fn("isAlpha",    lambda a: str(a[0]).isalpha()),
        "isAlNum":    _fn("isAlNum",    lambda a: str(a[0]).isalnum()),
        "format":     _fn("format",     lambda a: str(a[0]).format(*a[1:])),
        "count":      _fn("count",      lambda a: str(a[0]).count(str(a[1]))),
        "lines":      _fn("lines",      lambda a: PeeList(str(a[0]).splitlines())),
        "regexMatch": _fn("regexMatch", lambda a: bool(_re.match(str(a[1]), str(a[0])))),
        "regexFind":  _fn("regexFind",  lambda a: PeeList(_re.findall(str(a[1]), str(a[0])))),
        "regexReplace": _fn("regexReplace", lambda a: _re.sub(str(a[1]), str(a[2]), str(a[0]))),
        "toInt":      _fn("toInt",      lambda a: int(str(a[0]))),
        "toFloat":    _fn("toFloat",    lambda a: float(str(a[0]))),
        "chars":      _fn("chars",      lambda a: PeeList(list(str(a[0])))),
    }
    return PeeMap(data)
