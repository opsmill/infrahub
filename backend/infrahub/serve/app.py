"""Gunicorn entry point.

Gunicorn supports factory syntax via `"module:callable()"`, but the parentheses
require shell quoting that doesn't survive when the command is passed through
`sh -c "$COMMAND"` (as in `development/docker-compose.yml`). This thin module
exposes `app` so gunicorn can load it with plain `module:attribute` syntax.

Uvicorn consumers should target `infrahub.server:create_app` with `--factory`
instead of importing this module.
"""

from infrahub.server import create_app

app = create_app()
