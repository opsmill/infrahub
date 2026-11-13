from __future__ import annotations

from uuid import uuid4

from infrahub.core.diff.enricher.aggregated import AggregatedDiffEnricher
from infrahub.core.diff.enricher.interface import DiffEnricherInterface
from infrahub.core.diff.model.path import CalculatedDiffs, DiffRoot, EnrichedDiffRoot, NameTrackingId
from infrahub.core.timestamp import Timestamp


class RecordingEnricher(DiffEnricherInterface):
    def __init__(self) -> None:
        self.enriched_roots: list[EnrichedDiffRoot] = []

    async def enrich(self, enriched_diff_root: EnrichedDiffRoot, calculated_diffs: CalculatedDiffs) -> None:
        self.enriched_roots.append(enriched_diff_root)


def _calculated_root(branch: str) -> DiffRoot:
    return DiffRoot(from_time=Timestamp("2026-01-01T00:00:00Z"), to_time=Timestamp(), uuid=str(uuid4()), branch=branch)


async def test_diff_of_a_branch_against_itself_is_enriched_as_one_root() -> None:
    calculated_root = _calculated_root(branch="main")
    enricher = RecordingEnricher()

    enriched = await AggregatedDiffEnricher(enrichers=[enricher]).enrich(
        calculated_diffs=CalculatedDiffs(
            base_branch_name="main",
            diff_branch_name="main",
            base_branch_diff=calculated_root,
            diff_branch_diff=calculated_root,
        ),
        tracking_id=NameTrackingId(name="self-diff"),
    )

    assert enriched.base_branch_diff is enriched.diff_branch_diff
    assert enriched.roots == (enriched.diff_branch_diff,)
    assert len(enricher.enriched_roots) == 1
    assert enricher.enriched_roots[0] is enriched.diff_branch_diff


async def test_diff_of_two_branches_is_enriched_as_two_roots() -> None:
    enricher = RecordingEnricher()

    enriched = await AggregatedDiffEnricher(enrichers=[enricher]).enrich(
        calculated_diffs=CalculatedDiffs(
            base_branch_name="main",
            diff_branch_name="branch",
            base_branch_diff=_calculated_root(branch="main"),
            diff_branch_diff=_calculated_root(branch="branch"),
        ),
        tracking_id=NameTrackingId(name="pair-diff"),
    )

    assert enriched.base_branch_diff is not enriched.diff_branch_diff
    assert len(enricher.enriched_roots) == 2
    assert enricher.enriched_roots[0] is enriched.base_branch_diff
    assert enricher.enriched_roots[1] is enriched.diff_branch_diff
