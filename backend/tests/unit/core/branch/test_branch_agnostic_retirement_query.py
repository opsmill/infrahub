"""The shape of the branch-delete retirement query, which decides how much memory it can need.

The candidate stream stays unaggregated and the retention evaluation runs inside the transactional
batch, so a run's memory is bounded by the batch rather than by the branch. These assertions pin
that shape.
"""

from __future__ import annotations

import re

from infrahub.core.query.agnostic_retention import (
    RETAINING_BRANCHES_MATCH,
    UNRETAINED_AGNOSTIC_FIELD_EVALUATION,
)
from infrahub.core.query.branch_agnostic_retirement import _RETIRE_UNRETAINED_FIELDS_OF_BRANCH

BATCH_OPENING = "CALL (reachable_node, branch_windows) {"
BATCH_CLOSING = "} IN TRANSACTIONS OF $batch_size ROWS"


def _without_comments(cypher: str) -> str:
    return re.sub(r"//[^\n]*", "", cypher).strip()


def _split_around_batch() -> tuple[str, str, str]:
    # Cypher comments explain the shape; they must not satisfy or defeat the assertions about it.
    cypher = re.sub(r"//[^\n]*", "", _RETIRE_UNRETAINED_FIELDS_OF_BRANCH)
    outer, _, rest = cypher.partition(BATCH_OPENING)
    batch, _, tail = rest.partition(BATCH_CLOSING)
    assert outer, "the query starts with an outer stream"
    assert batch, "the outer stream feeds one transactional batch"
    assert tail, "the batch is what the query ends with"
    return outer, batch, tail


def test_the_retention_evaluation_runs_inside_the_transactional_batch() -> None:
    _, batch, _ = _split_around_batch()
    assert _without_comments(UNRETAINED_AGNOSTIC_FIELD_EVALUATION) in batch
    assert "collect(DISTINCT field) AS agnostic_candidates" in batch, (
        "each batch collects only the fields of its own nodes"
    )


def test_the_outer_stream_holds_nothing_per_candidate() -> None:
    outer, _, _ = _split_around_batch()
    assert "DISTINCT" not in outer, "a DISTINCT over the node stream retains every candidate for the whole run"
    assert outer.count("collect(") == 1, "the only aggregation before the batch is the branch-window list"
    assert _without_comments(RETAINING_BRANCHES_MATCH) in outer, "the retaining branches are read once and imported"
    assert _without_comments(UNRETAINED_AGNOSTIC_FIELD_EVALUATION) not in outer


def test_the_batch_closes_only_global_edges_at_the_run_stamp() -> None:
    _, batch, tail = _split_around_batch()
    assert "SET edge_to_close.to = $at, edge_to_close.to_user_id = $user_id" in batch
    assert "edge_to_close.branch = $global_branch_name" in batch
    assert "RETURN sum(batch_closed_edges) AS edges_closed" in tail
