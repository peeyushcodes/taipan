"""
Taipan Standard Library — File Module
"""
import os as _os
import pathlib as _pathlib
from taipan.runtime.taipan_types import PeeMap, PeeList, PeeFunction
from taipan.runtime.environment import Environment
from taipan.runtime.errors import TaipanRuntimeError


def get_module() -> PeeMap:
    env = Environment(name="stdlib:file")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    def _read(a):
        path = str(a[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except FileNotFoundError:
            raise TaipanRuntimeError(f"File not found: '{path}'")
        except PermissionError:
            raise TaipanRuntimeError(f"Permission denied: '{path}'")

    def _write(a):
        path, content = str(a[0]), str(a[1])
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return None

    def _append(a):
        path, content = str(a[0]), str(a[1])
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return None

    def _lines(a):
        path = str(a[0])
        try:
            with open(path, "r", encoding="utf-8") as f:
                return PeeList([l.rstrip("\n") for l in f.readlines()])
        except FileNotFoundError:
            raise TaipanRuntimeError(f"File not found: '{path}'")

    def _delete(a):
        path = str(a[0])
        try:
            _os.remove(path)
        except FileNotFoundError:
            raise TaipanRuntimeError(f"File not found: '{path}'")
        return None

    def _listdir(a):
        path = str(a[0]) if a else "."
        try:
            return PeeList(sorted(_os.listdir(path)))
        except FileNotFoundError:
            raise TaipanRuntimeError(f"Directory not found: '{path}'")

    data = {
        "read":      _fn("read",      _read),
        "write":     _fn("write",     _write),
        "append":    _fn("append",    _append),
        "lines":     _fn("lines",     _lines),
        "delete":    _fn("delete",    _delete),
        "exists":    _fn("exists",    lambda a: _os.path.exists(str(a[0]))),
        "isFile":    _fn("isFile",    lambda a: _os.path.isfile(str(a[0]))),
        "isDir":     _fn("isDir",     lambda a: _os.path.isdir(str(a[0]))),
        "mkdir":     _fn("mkdir",     lambda a: _os.makedirs(str(a[0]), exist_ok=True) or None),
        "listDir":   _fn("listDir",   _listdir),
        "cwd":       _fn("cwd",       lambda a: _os.getcwd()),
        "join":      _fn("join",      lambda a: _os.path.join(*[str(x) for x in a])),
        "basename":  _fn("basename",  lambda a: _os.path.basename(str(a[0]))),
        "dirname":   _fn("dirname",   lambda a: _os.path.dirname(str(a[0]))),
        "extension": _fn("extension", lambda a: _os.path.splitext(str(a[0]))[1]),
        "size":      _fn("size",      lambda a: _os.path.getsize(str(a[0]))),
        "rename":    _fn("rename",    lambda a: _os.rename(str(a[0]), str(a[1])) or None),
        "copy":      _fn("copy",      lambda a: __import__("shutil").copy2(str(a[0]), str(a[1])) and None),
    }
    return PeeMap(data)
