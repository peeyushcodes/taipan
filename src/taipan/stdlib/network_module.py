"""
Taipan Standard Library — Network Module
"""
from taipan.runtime.taipan_types import PeeMap, PeeFunction
from taipan.runtime.environment import Environment
from taipan.runtime.errors import TaipanRuntimeError


def get_module() -> PeeMap:
    env = Environment(name="stdlib:network")

    def _fn(name, fn):
        return PeeFunction(name=name, params=[], body=None, closure=env,
                           is_builtin=True, builtin_fn=fn)

    def _get(a):
        url     = str(a[0])
        headers = {}
        if len(a) > 1 and hasattr(a[1], '_data'):
            headers = {str(k): str(v) for k, v in a[1]._data.items()}
        try:
            import urllib.request, urllib.error
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except ImportError:
            raise TaipanRuntimeError("urllib not available")
        except Exception as e:
            raise TaipanRuntimeError(f"HTTP GET failed: {e}")

    def _post(a):
        url  = str(a[0])
        body = str(a[1]) if len(a) > 1 else ""
        try:
            import urllib.request, urllib.error
            data = body.encode("utf-8")
            req  = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            raise TaipanRuntimeError(f"HTTP POST failed: {e}")

    def _download(a):
        url  = str(a[0])
        dest = str(a[1]) if len(a) > 1 else url.split("/")[-1]
        try:
            import urllib.request
            urllib.request.urlretrieve(url, dest)
            return dest
        except Exception as e:
            raise TaipanRuntimeError(f"Download failed: {e}")

    def _url_encode(a):
        try:
            from urllib.parse import quote
            return quote(str(a[0]), safe="")
        except Exception as e:
            raise TaipanRuntimeError(f"URL encode failed: {e}")

    data = {
        "get":       _fn("get",       _get),
        "post":      _fn("post",      _post),
        "download":  _fn("download",  _download),
        "urlEncode": _fn("urlEncode", _url_encode),
        "urlDecode": _fn("urlDecode", lambda a: __import__("urllib.parse", fromlist=["unquote"]).unquote(str(a[0]))),
        "ping":      _fn("ping",      lambda a: bool(_get([str(a[0])]))),
    }
    return PeeMap(data)
