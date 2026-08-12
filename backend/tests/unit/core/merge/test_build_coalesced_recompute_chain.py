"""Coalesced recompute selection across a multi-level computed-attribute chain.

The derivation needs only a processed schema branch, so these build one in memory.
"""

from __future__ import annotations

from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    RECOMPUTE_CHAIN_DEPTH_FLOOR,
    AffectedTarget,
    CoalescedRecompute,
    CoalescedRecomputeBuilder,
    MergeChange,
    max_recompute_chain_depth,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.merge_recompute.dataset import build_chain_schema, build_python_only_schema, chain_kind


def _chain_schema_branch(levels: int = 3) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=build_chain_schema(levels=levels))
    schema_branch.process()
    return schema_branch


def _python_only_schema_branch(attribute_count: int) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(schema=build_python_only_schema(attribute_count=attribute_count))
    schema_branch.process()
    return schema_branch


def _identities(result: CoalescedRecompute) -> set[tuple[str, str, str | None]]:
    return {(target.family, target.target_kind, target.attribute_name) for target in result.targets}


def _lookups(target: AffectedTarget) -> set[tuple[str, str, frozenset[str]]]:
    return {(lookup.source_kind, lookup.filter_key, lookup.source_node_ids) for lookup in target.reader_lookups}


def test_root_change_reaches_only_the_first_hop() -> None:
    """A change confined to the root derives the first reader only; deeper levels are not in the diff."""
    builder = CoalescedRecomputeBuilder(schema_branch=_chain_schema_branch())
    l1, l2 = chain_kind(1), chain_kind(2)
    changes = [MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"}))]

    result = builder.build(changes=changes, branch="main")

    assert _identities(result) == {(COMPUTED_ATTRIBUTE, l2, "summary")}
    target = next(iter(result.targets))
    assert target.reads_across_relationship is True
    assert _lookups(target) == {(l1, "source__ids", frozenset({"l1-0"}))}


def test_intermediate_change_reaches_the_next_hop() -> None:
    """A diff carrying the intermediate summary derives the next hop, so a branch cascade stays coalesced."""
    builder = CoalescedRecomputeBuilder(schema_branch=_chain_schema_branch())
    l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)
    changes = [
        MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="l2-0", kind=l2, action="updated", changed_fields=frozenset({"summary"})),
    ]

    result = builder.build(changes=changes, branch="main")

    assert _identities(result) == {
        (COMPUTED_ATTRIBUTE, l2, "summary"),
        (COMPUTED_ATTRIBUTE, l3, "summary"),
    }


def test_full_chain_diff_covers_each_reader_level_once() -> None:
    """A diff carrying every level derives each reader level once, reached only by the level below.

    The l3 change reaches no target because the tip has no reader, so it does not fan out past the
    end of the chain.
    """
    builder = CoalescedRecomputeBuilder(schema_branch=_chain_schema_branch())
    l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)
    changes = [
        MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="l2-0", kind=l2, action="updated", changed_fields=frozenset({"summary"})),
        MergeChange(node_id="l3-0", kind=l3, action="updated", changed_fields=frozenset({"summary"})),
    ]

    result = builder.build(changes=changes, branch="main")

    targets = {(target.target_kind, target.attribute_name): target for target in result.targets}
    assert set(targets) == {(l2, "summary"), (l3, "summary")}
    assert _lookups(targets[l2, "summary"]) == {(l1, "source__ids", frozenset({"l1-0"}))}
    assert _lookups(targets[l3, "summary"]) == {(l2, "source__ids", frozenset({"l2-0"}))}


def test_depth_bound_counts_python_attributes() -> None:
    """A schema whose only derived values are Python transforms gets a bound that covers them all.

    The bound exists to stop a cyclic schema without ever truncating a real chain, and that
    second half only holds if every family it can chain through is counted.
    """
    attribute_count = RECOMPUTE_CHAIN_DEPTH_FLOOR + 5
    schema_branch = _python_only_schema_branch(attribute_count=attribute_count)

    assert max_recompute_chain_depth(schema_branch) == attribute_count
