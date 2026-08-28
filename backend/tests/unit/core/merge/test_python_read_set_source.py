"""Assembling the read-set index from the declared attributes and the analyzed queries.

The schema says which attributes exist, the transform queries say what each reads, and the two
arrive separately. What is pinned here is what happens when the second half is incomplete: one
unresolved transform drops its own attribute, while a failed analysis widens all of them.
"""

from __future__ import annotations

from infrahub.core.merge.python_target_sources import DatabasePythonReadSetSource, DeclaredAttribute
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from tests.adapters.python_target_sources import (
    FailingAnalyzedPythonReadSets,
    StaticAnalyzedPythonReadSets,
    StaticDeclaredPythonAttributes,
)

BRANCH = "main"
DEVICE = "TestingDevice"
SUMMARY = DeclaredAttribute(kind=DEVICE, attribute_name="summary")
DIGEST = DeclaredAttribute(kind=DEVICE, attribute_name="digest")
SUMMARY_READS = TransformReadSet(read_kinds=frozenset({DEVICE}), read_fields={DEVICE: frozenset({"name"})})


def _source(
    *, declared: list[DeclaredAttribute], analyzed: dict[DeclaredAttribute, TransformReadSet] | None = None
) -> DatabasePythonReadSetSource:
    return DatabasePythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=declared),
        read_sets=StaticAnalyzedPythonReadSets(analyzed=analyzed or {}),
    )


async def test_an_analyzed_attribute_keeps_its_read_set() -> None:
    source = _source(declared=[SUMMARY], analyzed={SUMMARY: SUMMARY_READS})

    read_sets = await source.read_sets(branch=BRANCH)

    assert [(entry.kind, entry.attribute_name) for entry in read_sets] == [(DEVICE, "summary")]
    assert read_sets[0].read_set == SUMMARY_READS
    assert read_sets[0].gathered is True


async def test_an_attribute_the_analysis_skipped_is_left_out() -> None:
    """An attribute with no transform to compute it stays out of the pass.

    Nothing can render its value until the transform arrives, and the recompute that follows the
    transform being created is what covers it then.
    """
    source = _source(declared=[SUMMARY, DIGEST], analyzed={SUMMARY: SUMMARY_READS})

    read_sets = await source.read_sets(branch=BRANCH)

    assert [(entry.kind, entry.attribute_name) for entry in read_sets] == [(DEVICE, "summary")]
    assert read_sets[0].read_set == SUMMARY_READS


async def test_a_failed_analysis_widens_every_declared_attribute() -> None:
    """The analysis resolves its peers strictly, so one missing peer raises for all of them.

    Each declared attribute is then reported undeterminable and recomputed over its whole kind.
    """
    analyzed = FailingAnalyzedPythonReadSets()
    source = DatabasePythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=[SUMMARY, DIGEST]), read_sets=analyzed
    )

    read_sets = await source.read_sets(branch=BRANCH)

    assert analyzed.calls == [BRANCH]
    assert {entry.attribute_name for entry in read_sets} == {"summary", "digest"}
    assert all(entry.read_set.depends_on_everything for entry in read_sets)
    assert not any(entry.gathered for entry in read_sets)


async def test_a_branch_declaring_nothing_never_reaches_the_analysis() -> None:
    analyzed = StaticAnalyzedPythonReadSets(analyzed={})
    source = DatabasePythonReadSetSource(
        declared_attributes=StaticDeclaredPythonAttributes(declared=[]), read_sets=analyzed
    )

    assert await source.read_sets(branch=BRANCH) == []
    assert analyzed.calls == []
