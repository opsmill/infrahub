"""Serving layer for the Infrahub API.

The API server is served by the ``pingora-granian`` supervisor (a pure-Rust
Pingora gateway header-routing to per-tier Granian worker pools over Unix
sockets) — see ``development/infrahub-serve.sh``. The previous gunicorn glue
(``gunicorn_config.py``, the ``InfrahubUvicorn`` worker, and the
``GunicornLogger``) has been removed; the prometheus-multiproc cleanup it used to
do per worker is re-homed to that launcher.
"""
