"""
Taipan Standard Library — Time Module
"""
import time as _time
import datetime as _dt
from taipan.runtime.taipan_types import PeeMap, PeeFunction
from taipan.runtime.environment import Environment


def get_module() -> PeeMap:
    env = Environment(name="stdlib:time")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    data = {
        "now":       _fn("now",       lambda a: _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "timestamp": _fn("timestamp", lambda a: _time.time()),
        "sleep":     _fn("sleep",     lambda a: _time.sleep(float(a[0])) or None),
        "date":      _fn("date",      lambda a: _dt.date.today().isoformat()),
        "year":      _fn("year",      lambda a: _dt.datetime.now().year),
        "month":     _fn("month",     lambda a: _dt.datetime.now().month),
        "day":       _fn("day",       lambda a: _dt.datetime.now().day),
        "hour":      _fn("hour",      lambda a: _dt.datetime.now().hour),
        "minute":    _fn("minute",    lambda a: _dt.datetime.now().minute),
        "second":    _fn("second",    lambda a: _dt.datetime.now().second),
        "format":    _fn("format",    lambda a: _dt.datetime.now().strftime(str(a[0]))),
        "since":     _fn("since",     lambda a: _time.time() - float(a[0])),
        "clock":     _fn("clock",     lambda a: _time.perf_counter()),
    }
    return PeeMap(data)
