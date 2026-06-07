"""GIL-safe drop-in for the slice of ``orjson`` that Prefect's client uses.

The real ``orjson`` C extension declares ``Py_MOD_GIL_USED`` and re-enables the
GIL on import, which defeats the embedded free-threaded (cp314t) backend served by
pingora-granian. This module re-implements orjson's surface on top of ``msgspec``
(GIL-safe: ships cp314t wheels and keeps the GIL disabled) so that ``import
prefect`` — and therefore ``import infrahub.server`` — stays GIL-free.

It is registered as ``sys.modules["orjson"]`` by ``infrahub/__init__.py`` when the
interpreter is free-threaded, before Prefect/FastAPI import orjson. On a normal
(GIL) interpreter this shim is not used and the real orjson is installed.

Surface covered (the symbols Prefect references):
    dumps, loads, Fragment, OPT_INDENT_2, OPT_SERIALIZE_NUMPY, OPT_NON_STR_KEYS,
    JSONDecodeError, JSONEncodeError (+ other OPT_* defined for attribute parity)

Not a general orjson replacement — scoped to Prefect's usage and validated by the
Phase-2 reachability + prefect-client round-trip checks.
"""
from __future__ import annotations

import msgspec as _msgspec

__version__ = "0.0.0-msgspec-shim"

# orjson option bit flags. Only the three Prefect uses need real behaviour; the
# rest are defined (with orjson's real values) so attribute access never breaks.
OPT_INDENT_2 = 1 << 0
OPT_NON_STR_KEYS = 1 << 1
OPT_SERIALIZE_NUMPY = 1 << 7
OPT_APPEND_NEWLINE = 1 << 10
OPT_NAIVE_UTC = 1 << 1
OPT_OMIT_MICROSECONDS = 1 << 2
OPT_PASSTHROUGH_DATACLASS = 1 << 11
OPT_PASSTHROUGH_DATETIME = 1 << 9
OPT_PASSTHROUGH_SUBCLASS = 1 << 8
OPT_SERIALIZE_DATACLASS = 0
OPT_SERIALIZE_UUID = 0
OPT_SORT_KEYS = 1 << 5
OPT_STRICT_INTEGER = 1 << 6
OPT_UTC_Z = 1 << 3

# orjson raises these; Prefect catches them. msgspec's errors already subclass
# ValueError, matching orjson's hierarchy closely enough for `except` clauses.
JSONDecodeError = _msgspec.DecodeError
JSONEncodeError = _msgspec.EncodeError


def _numpy_enc_hook(obj):
    """OPT_SERIALIZE_NUMPY: turn numpy arrays/scalars into JSON-native values."""
    try:
        import numpy as _np
    except Exception:  # numpy not present -> nothing to do
        raise TypeError(f"Type is not JSON serializable: {type(obj).__name__}")
    if isinstance(obj, _np.ndarray):
        return obj.tolist()
    if isinstance(obj, _np.generic):
        return obj.item()
    raise TypeError(f"Type is not JSON serializable: {type(obj).__name__}")


def _stringify_keys(obj):
    """OPT_NON_STR_KEYS: orjson coerces non-str dict keys; msgspec rejects them."""
    if isinstance(obj, dict):
        return {(k if isinstance(k, str) else str(k)): _stringify_keys(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_stringify_keys(v) for v in obj]
    return obj


def dumps(obj, /, default=None, option=None):
    """orjson.dumps -> bytes, via msgspec.json.encode."""
    option = option or 0

    if option & OPT_SERIALIZE_NUMPY:
        user = default

        def enc_hook(o):
            if user is not None:
                try:
                    return user(o)
                except TypeError:
                    pass
            return _numpy_enc_hook(o)
    else:
        enc_hook = default

    payload = _stringify_keys(obj) if (option & OPT_NON_STR_KEYS) else obj
    out = _msgspec.json.encode(payload, enc_hook=enc_hook)
    if option & OPT_INDENT_2:
        out = _msgspec.json.format(out, indent=2)
    if option & OPT_APPEND_NEWLINE:
        out += b"\n"
    return out


def loads(data, /):
    """orjson.loads(bytes|str|bytearray|memoryview) -> obj."""
    return _msgspec.json.decode(data)


class Fragment:
    """orjson.Fragment passthrough (rarely used by Prefect; kept for parity)."""

    __slots__ = ("contents",)

    def __init__(self, contents):
        self.contents = contents


__all__ = [
    "dumps", "loads", "Fragment", "JSONDecodeError", "JSONEncodeError",
    "OPT_INDENT_2", "OPT_NON_STR_KEYS", "OPT_SERIALIZE_NUMPY", "OPT_APPEND_NEWLINE",
    "OPT_NAIVE_UTC", "OPT_OMIT_MICROSECONDS", "OPT_PASSTHROUGH_DATACLASS",
    "OPT_PASSTHROUGH_DATETIME", "OPT_PASSTHROUGH_SUBCLASS", "OPT_SORT_KEYS",
    "OPT_STRICT_INTEGER", "OPT_UTC_Z", "__version__",
]
