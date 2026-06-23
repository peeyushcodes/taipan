"""
Taipan Standard Library — Math Module
"""
import math as _math
from taipan.runtime.taipan_types import PeeMap, PeeList, PeeFunction
from taipan.runtime.environment import Environment


def _wrap(fn):
    """Wrap a Python callable as a Taipan built-in function."""
    env = Environment(name="stdlib:math")
    return PeeFunction(
        name=fn.__name__, params=[], body=None, closure=env,
        is_builtin=True, builtin_fn=lambda args: fn(*args)
    )


def get_module() -> PeeMap:
    fns = {
        "sqrt":    lambda args: _math.sqrt(float(args[0])),
        "pow":     lambda args: _math.pow(float(args[0]), float(args[1])),
        "abs":     lambda args: abs(args[0]),
        "floor":   lambda args: _math.floor(float(args[0])),
        "ceil":    lambda args: _math.ceil(float(args[0])),
        "round":   lambda args: round(float(args[0]), int(args[1]) if len(args) > 1 else 0),
        "log":     lambda args: _math.log(float(args[0]), float(args[1])) if len(args) > 1 else _math.log(float(args[0])),
        "log2":    lambda args: _math.log2(float(args[0])),
        "log10":   lambda args: _math.log10(float(args[0])),
        "sin":     lambda args: _math.sin(float(args[0])),
        "cos":     lambda args: _math.cos(float(args[0])),
        "tan":     lambda args: _math.tan(float(args[0])),
        "asin":    lambda args: _math.asin(float(args[0])),
        "acos":    lambda args: _math.acos(float(args[0])),
        "atan":    lambda args: _math.atan(float(args[0])),
        "atan2":   lambda args: _math.atan2(float(args[0]), float(args[1])),
        "exp":     lambda args: _math.exp(float(args[0])),
        "factorial": lambda args: _math.factorial(int(args[0])),
        "gcd":     lambda args: _math.gcd(int(args[0]), int(args[1])),
        "lcm":     lambda args: (_math.lcm(int(args[0]), int(args[1])) if hasattr(_math, 'lcm') else abs(int(args[0]) * int(args[1])) // _math.gcd(int(args[0]), int(args[1]))),
        "isnan":   lambda args: _math.isnan(float(args[0])),
        "isinf":   lambda args: _math.isinf(float(args[0])),
        "hypot":   lambda args: _math.hypot(*[float(a) for a in args]),
        "clamp":   lambda args: max(float(args[1]), min(float(args[2]), float(args[0]))),
        "lerp":    lambda args: float(args[0]) + (float(args[1]) - float(args[0])) * float(args[2]),
        "degrees": lambda args: _math.degrees(float(args[0])),
        "radians": lambda args: _math.radians(float(args[0])),
        "random":  lambda args: __import__("random").random(),
        "randint": lambda args: __import__("random").randint(int(args[0]), int(args[1])),
        "pi":      _math.pi,
        "e":       _math.e,
        "tau":     _math.tau,
        "inf":     _math.inf,
    }

    env = Environment(name="stdlib:math")
    data = {}
    for name, val in fns.items():
        if callable(val):
            fn = val  # capture
            data[name] = PeeFunction(
                name=name, params=[], body=None, closure=env,
                is_builtin=True, builtin_fn=fn
            )
        else:
            data[name] = val  # constants like pi, e

    return PeeMap(data)
