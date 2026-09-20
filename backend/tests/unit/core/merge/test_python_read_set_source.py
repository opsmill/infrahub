"""Joining the declared attributes with the analyzed queries.

The schema says which attributes exist, the transform queries say what each reads, and the two
arrive separately. What is pinned here is what happens when the second half is incomplete: one
unresolved transform drops its own attribute, while a failed analysis widens all of them.
"""

from __future__ import annotations

from infrahub.core.merge.python_target_sources import AnalyzedRead, ComposedPythonReadSetSource, DeclaredAttribute
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from tests.adapters.python_target_sources import (
    FailingAnalyzedPythonReadSets,
    StaticAnalyzedPythonReadSets,
    StaticDeclaredPythonAttributes,
)

BRANCH = "main"
DEVICE = "TestingDevice"
SUMMARY = DeclaredAttribute(kind=DEVICE, attribute_name="summary")
ROSTER = DeclaredAttribute(kind=DEVICE, attribute_name="roster")
DIGEST = DeclaredAttribute(kind=DEVICE, attribute_name="digest")
DEVICE_READS = TransformReadSet(read_kinds=frozenset({DEVICE}), read_fields={DEVICE: frozenset({"name"})})
SUMMARY_READ = AnalyzedRead(read_set=DEVICE_READS, pinned=True)
ROSTER_READ = AnalyzedRead(read_set=DEVICE_READS, pinned=False)


def _source(
    *, declared: list[DeclaredAttribute], analyzed: dict[DeclaredAttribute, AnalyzedRead] | None = None
) -> ComposedPythonReadSetSource:
    return ComposedPythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=declared),
        analyzed_reads=StaticAnalyzedPythonReadSets(analyzed=analyzed or {}),
    )


async def test_an_attribute_the_analysis_skipped_is_left_out() -> None:
    """An attribute with no transform to compute it stays out of the pass.

    Nothing can render its value until the transform arrives, and the recompute that follows the
    transform being created is what covers it then. The two the analysis did answer for keep both
    of its findings: what the query reads, and whether its root is pinned.
    """
    source = _source(declared=[SUMMARY, ROSTER, DIGEST], analyzed={SUMMARY: SUMMARY_READ, ROSTER: ROSTER_READ})

    read_sets = {entry.attribute_name: entry for entry in await source.read_sets(branch=BRANCH)}

    assert set(read_sets) == {"summary", "roster"}
    assert read_sets["summary"].read_set == DEVICE_READS
    assert read_sets["summary"].gathered is True
    assert read_sets["summary"].pinned is True
    assert read_sets["roster"].pinned is False


async def test_a_failed_analysis_widens_every_declared_attribute() -> None:
    """The analysis resolves its peers strictly, so one missing peer raises for all of them.

    Each declared attribute is then reported undeterminable and recomputed over its whole kind.
    """
    analyzed = FailingAnalyzedPythonReadSets()
    source = ComposedPythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=[SUMMARY, DIGEST]), analyzed_reads=analyzed
    )

    read_sets = await source.read_sets(branch=BRANCH)

    assert analyzed.calls == [BRANCH]
    assert {entry.attribute_name for entry in read_sets} == {"summary", "digest"}
    assert all(entry.read_set.depends_on_everything for entry in read_sets)
    assert not any(entry.gathered for entry in read_sets)


async def test_a_branch_declaring_nothing_never_reaches_the_analysis() -> None:
    analyzed = StaticAnalyzedPythonReadSets(analyzed={})
    source = ComposedPythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=[]), analyzed_reads=analyzed
    )

    assert await source.read_sets(branch=BRANCH) == []
    assert analyzed.calls == []
