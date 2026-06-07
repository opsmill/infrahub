import sys

# Free-threaded (cp314t) support for the pingora-granian embedded backend.
# The real `orjson` C extension declares Py_MOD_GIL_USED and re-enables the GIL on
# import, which silently nullifies free-threading. Under a free-threaded
# interpreter, route `orjson` to a GIL-safe msgspec-backed shim BEFORE anything
# (Prefect, FastAPI) imports it. No-op on a normal (GIL) interpreter.
if not getattr(sys, "_is_gil_enabled", lambda: True)():
    from infrahub._compat import orjson_shim as _orjson_shim

    sys.modules.setdefault("orjson", _orjson_shim)

import importlib.metadata

__version__ = importlib.metadata.version("infrahub-server")
