"""Immutable measurement records for the merge/rebase recompute profile."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecomputeCounts:
    """Counting-layer signal for one merge or rebase at one scale."""

    changed_nodes: int
    node_events: dict[str, int]
    expected_recompute: dict[str, int]
    total_node_events: int
    total_expected_recompute: int

    @classmethod
    def build(
        cls, *, changed_nodes: int, node_events: dict[str, int], expected_recompute: dict[str, int]
    ) -> RecomputeCounts:
        return cls(
            changed_nodes=changed_nodes,
            node_events=dict(node_events),
            expected_recompute=dict(expected_recompute),
            total_node_events=sum(node_events.values()),
            total_expected_recompute=sum(expected_recompute.values()),
        )


@dataclass(frozen=True)
class CostCenterTiming:
    """Timing-layer wall-clock attribution for one merge at one scale.

    ``schema_migration_s`` is ``None`` for a data-only merge; ``db_commit_s`` is
    ``None`` when finer attribution is unavailable. ``recompute_flow_runs`` is the
    authoritative executed-recompute count.
    """

    merge_critical_path_s: float
    recompute_total_s: float
    recompute_window_s: float
    recompute_flow_runs: int
    schema_migration_s: float | None = None
    db_commit_s: float | None = None


@dataclass(frozen=True)
class ProfileRun:
    """One merge or rebase at one scale, carrying whichever layers ran."""

    operation: str
    scale_label: str
    changed_nodes: int
    schema_changing: bool
    tolerance_note: str
    counts: RecomputeCounts | None = None
    timing: CostCenterTiming | None = None


@dataclass(frozen=True)
class FindingsReport:
    """Aggregate across scales, serialized to findings.md."""

    runs: list[ProfileRun]
    dominant_cost_center: str
    growth_classification: dict[str, str]
    notes: str


def classify_growth(points: list[tuple[int, float]], *, linear_tolerance: float = 1.5) -> str:
    """Classify how a metric grows against the changed-node count.

    ``points`` are ``(changed_nodes, metric_value)`` pairs. Returns "flat" when
    the metric does not move with the node count, "linear" when value/nodes stays
    roughly constant (within ``linear_tolerance``), "super-linear" when that ratio
    rises with scale, and "sub-linear" otherwise.

    Raises:
        ValueError: if fewer than two distinct changed-node counts are given.

    """
    ordered = sorted(points)
    if len({nodes for nodes, _ in ordered}) < 2:
        raise ValueError("classify_growth needs at least two distinct changed-node counts")

    values = [float(value) for _, value in ordered]
    if max(values) == 0:
        return "flat"
    if max(values) - min(values) <= 1e-9:
        return "flat"

    ratios = [value / nodes for nodes, value in ordered if nodes]
    low, high = min(ratios), max(ratios)
    if low > 0 and high / low <= linear_tolerance:
        return "linear"
    if ratios[-1] > ratios[0]:
        return "super-linear"
    return "sub-linear"
