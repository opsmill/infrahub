"""Compatibility shims for the free-threaded (cp314t) embedded backend.

See ``orjson_shim`` — a GIL-safe stand-in for the slice of ``orjson`` that Prefect
uses, registered as ``sys.modules["orjson"]`` from ``infrahub/__init__.py`` when
running on a free-threaded interpreter.
"""
