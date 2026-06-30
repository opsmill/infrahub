"""Shared scale set for the merge/rebase recompute profile."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Scale:
    name: str
    changed_nodes: int


# Canonical set used by the timing layer (on demand). The large scale is where
# the per-node fan-out is meant to bite.
SCALES: list[Scale] = [
    Scale(name="small", changed_nodes=10),
    Scale(name="medium", changed_nodes=100),
    Scale(name="large", changed_nodes=1000),
]

# Subset the counting-layer determinism guard runs in CI. The large (1000-node)
# merge is too slow to drive node-by-node on every CI run; cardinality growth is
# already linear and visible at small/medium, and the timing layer covers 1000+.
CI_SCALES: list[Scale] = [
    Scale(name="small", changed_nodes=10),
    Scale(name="medium", changed_nodes=100),
]
