"""Selection logic for the coalesced merge/rebase recompute.

Drives ``build_coalesced_recompute`` over a registered profile schema and asserts
the deduplicated target set, with no task worker. The profile schema carries all
three families on one kind: a Jinja2 computed attribute and a display label that
both read a peer across a relationship, and a human-friendly id built from the
local name only. That mix exercises cross-node fan-out, the per-family difference
(the human-friendly id does not fan out on a related change), creation, deletion,
coalescing, and the bounded fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core import registry
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    DISPLAY_LABEL,
    HFID,
    AffectedTarget,
    CoalescedRecompute,
    MergeChange,
    build_coalesced_recompute,
)
from tests.helpers.merge_recompute.dataset import PROFILE_NODE_KIND, PROFILE_PEER_KIND, load_profile_schema

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.database import InfrahubDatabase


def _by_identity(result: CoalescedRecompute) -> dict[tuple[str, str, str | None], AffectedTarget]:
    return {(target.family, target.target_kind, target.attribute_name): target for target in result.targets}


def _lookups(target: AffectedTarget) -> set[tuple[str, frozenset[str]]]:
    return {(lookup.filter_key, lookup.source_node_ids) for lookup in target.reader_lookups}


async def _profile_schema_branch(db: InfrahubDatabase) -> SchemaBranch:
    await load_profile_schema(db=db)
    return registry.schema.get_schema_branch(name=registry.default_branch)


async def test_cross_node_update_coalesces_readers(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Many changed peers collapse to one computed and one display target, one union lookup each."""
    schema_branch = await _profile_schema_branch(db=db)
    peer_ids = {f"peer-{index:02d}" for index in range(5)}
    changes = [
        MergeChange(node_id=peer_id, kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
        for peer_id in peer_ids
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert target.reads_across_relationship is True
        assert _lookups(target) == {("peer__ids", frozenset(peer_ids))}
    assert result.fallback_used is False


async def test_same_node_update_has_no_async_targets(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A node's own change recomputes inline on save, so it adds nothing to the coalesced set."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [
        MergeChange(
            node_id=f"node-{index:02d}", kind=PROFILE_NODE_KIND, action="updated", changed_fields=frozenset({"name"})
        )
        for index in range(5)
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert result.targets == frozenset()


async def test_creation_fans_out_to_all_families(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A created node recomputes its own computed attribute, display label, and human-friendly id."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [MergeChange(node_id="node-new", kind=PROFILE_NODE_KIND, action="created")]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
        (HFID, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert target.reads_across_relationship is False
        assert _lookups(target) == {("ids", frozenset({"node-new"}))}


async def test_deleted_node_refreshes_readers(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """Deleting a peer recomputes the readers that read it, so their values no longer reflect it."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [MergeChange(node_id="peer-gone", kind=PROFILE_PEER_KIND, action="deleted")]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert _lookups(target) == {("peer__ids", frozenset({"peer-gone"}))}


async def test_hfid_does_not_fan_out_on_related_change(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """A human-friendly id built from the local name is never recomputed by a related node's change."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert not any(target.family == HFID for target in result.targets)


async def test_changes_to_same_target_are_deduplicated(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """An update and a deletion of peers reach the same target once, with their ids unioned."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="peer-1", kind=PROFILE_PEER_KIND, action="deleted"),
    ]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    computed = _by_identity(result)[COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"]
    assert _lookups(computed) == {("peer__ids", frozenset({"peer-0", "peer-1"}))}


async def test_update_without_fields_is_a_bounded_fallback(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
) -> None:
    """An update with no recorded fields recomputes every reader and is marked imprecise."""
    schema_branch = await _profile_schema_branch(db=db)
    changes = [MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset())]

    result = build_coalesced_recompute(changes=changes, schema_branch=schema_branch, branch="main")

    assert result.targets != frozenset()
    assert result.fallback_used is True
    assert all(target.precise is False for target in result.targets)
