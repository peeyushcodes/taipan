"""
Taipan Standard Library — Collections Module
Provides Stack, Queue, LinkedList, and PriorityQueue
"""
import heapq as _heapq
from taipan.runtime.taipan_types import PeeMap, PeeList, PeeFunction, PeeInstance, PeeClass
from taipan.runtime.environment import Environment


def get_module() -> PeeMap:
    env = Environment(name="stdlib:collections")

    # ── Stack ──────────────────────────────────────────────────────────────────
    class _Stack:
        def __init__(self): self._data = []
        def pee_method(self, name, args):
            match name:
                case "push":    self._data.append(args[0]); return None
                case "pop":     return self._data.pop() if self._data else None
                case "peek":    return self._data[-1] if self._data else None
                case "isEmpty": return len(self._data) == 0
                case "size":    return len(self._data)
                case "clear":   self._data.clear(); return None
                case "toList":  return PeeList(self._data[::-1])
                case _: raise AttributeError(f"Stack has no method '{name}'")
        def __repr__(self): return f"Stack({self._data})"

    # ── Queue ──────────────────────────────────────────────────────────────────
    class _Queue:
        def __init__(self): self._data = []
        def pee_method(self, name, args):
            match name:
                case "enqueue": self._data.append(args[0]); return None
                case "dequeue": return self._data.pop(0) if self._data else None
                case "front":   return self._data[0] if self._data else None
                case "isEmpty": return len(self._data) == 0
                case "size":    return len(self._data)
                case "clear":   self._data.clear(); return None
                case "toList":  return PeeList(self._data[:])
                case _: raise AttributeError(f"Queue has no method '{name}'")
        def __repr__(self): return f"Queue({self._data})"

    # ── PriorityQueue ──────────────────────────────────────────────────────────
    class _PriorityQueue:
        def __init__(self): self._heap = []
        def pee_method(self, name, args):
            match name:
                case "push":    _heapq.heappush(self._heap, (float(args[0]), args[1] if len(args)>1 else args[0])); return None
                case "pop":     return _heapq.heappop(self._heap)[1] if self._heap else None
                case "peek":    return self._heap[0][1] if self._heap else None
                case "isEmpty": return len(self._heap) == 0
                case "size":    return len(self._heap)
                case _: raise AttributeError(f"PriorityQueue has no method '{name}'")
        def __repr__(self): return f"PriorityQueue(size={len(self._heap)})"

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    def _make_stack(a): return _Stack()
    def _make_queue(a): return _Queue()
    def _make_pq(a):    return _PriorityQueue()

    def _counter(a):
        """Count occurrences — returns a PeeMap."""
        lst = a[0]
        counts = {}
        if hasattr(lst, '_data'):
            for item in lst._data:
                counts[item] = counts.get(item, 0) + 1
        return PeeMap(counts)

    def _flatten(a):
        """Flatten a nested list one level."""
        lst = a[0]
        result = []
        if hasattr(lst, '_data'):
            for item in lst._data:
                if hasattr(item, '_data'):
                    result.extend(item._data)
                else:
                    result.append(item)
        return PeeList(result)

    def _unique(a):
        """Remove duplicates preserving order."""
        lst = a[0]
        seen = []
        result = []
        if hasattr(lst, '_data'):
            for item in lst._data:
                if item not in seen:
                    seen.append(item)
                    result.append(item)
        return PeeList(result)

    data = {
        "Stack":         _fn("Stack",         _make_stack),
        "Queue":         _fn("Queue",         _make_queue),
        "PriorityQueue": _fn("PriorityQueue", _make_pq),
        "counter":       _fn("counter",       _counter),
        "flatten":       _fn("flatten",       _flatten),
        "unique":        _fn("unique",        _unique),
        "zip":           _fn("zip",           lambda a: PeeList([PeeList(list(pair)) for pair in zip(*(x._data if hasattr(x,'_data') else x for x in a))])),
        "enumerate":     _fn("enumerate",     lambda a: PeeList([PeeList([i, v]) for i, v in enumerate(a[0]._data if hasattr(a[0],'_data') else a[0])])),
        "chunk":         _fn("chunk",         lambda a: PeeList([PeeList(a[0]._data[i:i+int(a[1])]) for i in range(0, len(a[0]._data), int(a[1]))])),
        "groupBy":       _fn("groupBy",       lambda a: PeeMap({})),   # placeholder
    }
    return PeeMap(data)
