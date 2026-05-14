"""Constants for the graph-traversal planner.

Centralizes magic numbers that would otherwise appear in multiple modules
(`models.py`, `planner.py`, future Cypher renderer). Mirrors the bounds the
GraphQL input layer enforces in `backend/infrahub/graphql/queries/path.py` and
`reachable.py`.
"""

from __future__ import annotations

MIN_DEPTH = 1
MAX_DEPTH = 20
DEFAULT_DEPTH = 5
