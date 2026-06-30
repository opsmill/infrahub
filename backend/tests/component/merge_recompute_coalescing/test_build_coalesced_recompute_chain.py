"""Coalesced recompute selection across a multi-level computed-attribute chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    AffectedTarget,
    CoalescedRecompute,
    MergeChange,
    build_coalesced_recompute,
)
from tests.helpers.merge_recompute.dataset import chain_kind, load_chain_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _identities(result: CoalescedRecompute) -> set[tuple[str, str, str | None]]:
    return {(target.family, target.target_kind, target.attribute_name) for target in result.targets}


def _lookups(target: AffectedTarget) -> set[tuple[str, str, frozenset[str]]]:
    return {(lookup.source_kind, lookup.filter_key, lookup.source_node_ids) for lookup in target.reader_lookups}


async def _chain_schema_branch(db: InfrahubDatabase, levels: int = 3) -> SchemaBranch:
    await load_chain_schema(db=db, levels=levels)
    return registry.schema.get_schema_branch(name=registry.default_branch)


async def test_root_change_reaches_only_the_first_hop(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A change confined to the root derives the first reader only; deeper levels are not in the diff."""
    schema_branch = await _chain_schema_branch(db=db)
    l1, l2 = chain_kind(1), chain_kind(2)
    changes = [MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"}))]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert _identities(result) == {(COMPUTED_ATTRIBUTE, l2, "summary")}
    target = next(iter(result.targets))
    assert target.reads_across_relationship is True
    assert _lookups(target) == {(l1, "source__ids", frozenset({"l1-0"}))}


async def test_intermediate_change_reaches_the_next_hop(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A diff carrying the intermediate summary derives the next hop, so a branch cascade stays coalesced."""
    schema_branch = await _chain_schema_branch(db=db)
    l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)
    changes = [
        MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="l2-0", kind=l2, action="updated", changed_fields=frozenset({"summary"})),
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert _identities(result) == {
        (COMPUTED_ATTRIBUTE, l2, "summary"),
        (COMPUTED_ATTRIBUTE, l3, "summary"),
    }


async def test_full_chain_diff_covers_each_reader_level_once(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A diff carrying every level derives one target per reader level; the chain tip reads nothing."""
    schema_branch = await _chain_schema_branch(db=db)
    l1, l2, l3 = chain_kind(1), chain_kind(2), chain_kind(3)
    changes = [
        MergeChange(node_id="l1-0", kind=l1, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="l2-0", kind=l2, action="updated", changed_fields=frozenset({"summary"})),
        MergeChange(node_id="l3-0", kind=l3, action="updated", changed_fields=frozenset({"summary"})),
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert _identities(result) == {
        (COMPUTED_ATTRIBUTE, l2, "summary"),
        (COMPUTED_ATTRIBUTE, l3, "summary"),
    }
