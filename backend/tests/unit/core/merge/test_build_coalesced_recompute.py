"""Selection logic for the coalesced merge/rebase recompute.

The derivation needs only a processed schema branch, so these are unit tests that build one in
memory rather than loading it through the database.
"""

from __future__ import annotations

from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    DISPLAY_LABEL,
    HFID,
    PYTHON_ATTRIBUTE,
    AffectedTarget,
    CoalescedRecompute,
    CoalescedRecomputeBuilder,
    MergeChange,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from tests.helpers.merge_recompute.dataset import (
    PROFILE_NODE_KIND,
    PROFILE_PEER_KIND,
    PROFILE_PYTHON_ATTRIBUTE,
    build_profile_schema,
)

PYTHON_TARGET = (PYTHON_ATTRIBUTE, PROFILE_NODE_KIND, PROFILE_PYTHON_ATTRIBUTE)


def _profile_schema_branch(cross_relationship_hfid: bool = False, python_attribute: bool = False) -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="test")
    schema_branch.load_schema(
        schema=build_profile_schema(cross_relationship_hfid=cross_relationship_hfid, python_attribute=python_attribute)
    )
    schema_branch.process()
    return schema_branch


def _by_identity(result: CoalescedRecompute) -> dict[tuple[str, str, str | None], AffectedTarget]:
    return {(target.family, target.target_kind, target.attribute_name): target for target in result.targets}


def _lookups(target: AffectedTarget) -> set[tuple[str, str, frozenset[str]]]:
    return {(lookup.source_kind, lookup.filter_key, lookup.source_node_ids) for lookup in target.reader_lookups}


def test_cross_node_update_coalesces_readers() -> None:
    """Many changed peers collapse to one computed and one display target, one union lookup each.

    The change set also carries kinds the derivation must tolerate rather than abort on: an updated
    profile kind (not a NodeSchema) and a kind absent from the branch. Neither adds a target here.
    """
    schema_branch = _profile_schema_branch()
    builder = CoalescedRecomputeBuilder(schema_branch=schema_branch)
    peer_ids = {f"peer-{index:02d}" for index in range(5)}
    changes = [
        MergeChange(node_id=peer_id, kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
        for peer_id in peer_ids
    ]
    changes.extend(
        [
            MergeChange(
                node_id="profile-0",
                kind=next(iter(schema_branch.profiles)),
                action="updated",
                changed_fields=frozenset({"name"}),
            ),
            MergeChange(
                node_id="ghost-0", kind="TestingMissingKind", action="updated", changed_fields=frozenset({"name"})
            ),
        ]
    )

    result = builder.build(changes=changes, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert target.reads_across_relationship is True
        assert _lookups(target) == {(PROFILE_PEER_KIND, "peer__ids", frozenset(peer_ids))}
    assert result.fallback_used is False


def test_same_node_update_has_no_async_targets() -> None:
    """A node's own change recomputes inline on save, so it adds nothing to the coalesced set."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [
        MergeChange(
            node_id=f"node-{index:02d}", kind=PROFILE_NODE_KIND, action="updated", changed_fields=frozenset({"name"})
        )
        for index in range(5)
    ]

    result = builder.build(changes=changes, branch="main")

    assert result.targets == frozenset()


def test_creation_fans_out_to_all_families() -> None:
    """A created node recomputes its own computed attribute, display label, and human-friendly id."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [MergeChange(node_id="node-new", kind=PROFILE_NODE_KIND, action="created")]

    result = builder.build(changes=changes, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
        (HFID, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert target.reads_across_relationship is False
        assert _lookups(target) == {(PROFILE_NODE_KIND, "ids", frozenset({"node-new"}))}


def test_deleted_node_refreshes_readers() -> None:
    """Deleting a peer recomputes the readers that read it, so their values no longer reflect it."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [MergeChange(node_id="peer-gone", kind=PROFILE_PEER_KIND, action="deleted")]

    result = builder.build(changes=changes, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert _lookups(target) == {(PROFILE_PEER_KIND, "peer__ids", frozenset({"peer-gone"}))}


def test_relationship_change_recomputes_own_values_by_id() -> None:
    """A relationship in an update's changed fields recomputes the node's own derived values by its id.

    This is the reader whose peer was deleted: it appears as an update on the relationship but was
    never saved, so its cross-relationship values are not refreshed inline.
    """
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [
        MergeChange(node_id="node-0", kind=PROFILE_NODE_KIND, action="updated", changed_fields=frozenset({"peer"}))
    ]

    result = builder.build(changes=changes, branch="main")

    # The relationship is in the changed fields, so this is the precise self path, not the fallback.
    assert result.fallback_used is False
    by_identity = _by_identity(result)
    own = {(PROFILE_NODE_KIND, "ids", frozenset({"node-0"}))}
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
        (HFID, PROFILE_NODE_KIND, None),
    }
    for target in by_identity.values():
        assert target.reads_across_relationship is False
        assert _lookups(target) == own


def test_hfid_does_not_fan_out_on_related_change() -> None:
    """A human-friendly id built from the local name is never recomputed by a related node's change."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    result = builder.build(changes=changes, branch="main")

    assert not any(target.family == HFID for target in result.targets)


def test_hfid_fans_out_when_id_crosses_relationship() -> None:
    """A human-friendly id that reads a peer across the relationship is recomputed by that peer's change.

    A merge and a rebase reach the builder identically, so this one derivation covers both: the reader's
    id is scheduled alongside the display label and computed attribute that read the same peer.
    """
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(cross_relationship_hfid=True))
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    result = builder.build(changes=changes, branch="main")

    hfid = _by_identity(result)[HFID, PROFILE_NODE_KIND, None]
    assert hfid.reads_across_relationship is True
    assert _lookups(hfid) == {(PROFILE_PEER_KIND, "peer__ids", frozenset({"peer-0"}))}


def test_changes_to_same_target_are_deduplicated() -> None:
    """An update and a deletion of peers reach the same target once, with their ids unioned."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"})),
        MergeChange(node_id="peer-1", kind=PROFILE_PEER_KIND, action="deleted"),
    ]

    result = builder.build(changes=changes, branch="main")

    computed = _by_identity(result)[COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"]
    assert _lookups(computed) == {(PROFILE_PEER_KIND, "peer__ids", frozenset({"peer-0", "peer-1"}))}


def test_unscoped_update_is_a_bounded_fallback() -> None:
    """An unscoped update imprecisely recomputes cross-node readers and the node's own derived values."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch())

    # A peer: its cross-node readers (node summary and display) plus its own derived values.
    peer_result = builder.build(
        changes=[MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset())],
        branch="main",
    )
    assert set(_by_identity(peer_result)) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
        (DISPLAY_LABEL, PROFILE_PEER_KIND, None),
        (HFID, PROFILE_PEER_KIND, None),
    }
    assert peer_result.fallback_used is True
    assert all(target.precise is False for target in peer_result.targets)

    # A node: its own derived values, keyed by its own id.
    node_result = builder.build(
        changes=[MergeChange(node_id="node-0", kind=PROFILE_NODE_KIND, action="updated", changed_fields=frozenset())],
        branch="main",
    )
    by_identity = _by_identity(node_result)
    own = {(PROFILE_NODE_KIND, "ids", frozenset({"node-0"}))}
    assert _lookups(by_identity[COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"]) == own
    assert _lookups(by_identity[DISPLAY_LABEL, PROFILE_NODE_KIND, None]) == own
    assert _lookups(by_identity[HFID, PROFILE_NODE_KIND, None]) == own
    assert node_result.fallback_used is True


def test_python_target_is_named_without_ids() -> None:
    """A peer change names the Python attribute and leaves its nodes to the resolution step.

    Which kinds a transform reads lives in its stored query, so the schema cannot say whether
    this peer is read, nor by which nodes.
    """
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(python_attribute=True))
    changes = [
        MergeChange(node_id="peer-0", kind=PROFILE_PEER_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    result = builder.build(changes=changes, branch="main")

    by_identity = _by_identity(result)
    assert set(by_identity) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
        PYTHON_TARGET,
    }
    python_target = by_identity[PYTHON_TARGET]
    assert python_target.reader_lookups == frozenset()
    assert python_target.whole_kind is False
    assert python_target.reads_across_relationship is True


def test_python_owner_axis_survives_an_update_the_other_families_drop() -> None:
    """A node's own change adds a Python target where the other three families add none.

    The save recomputes a template-derived value inline; a transform runs from an automation,
    so the coalesced pass is what has to schedule it.
    """
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(python_attribute=True))
    changes = [
        MergeChange(node_id="node-0", kind=PROFILE_NODE_KIND, action="updated", changed_fields=frozenset({"name"}))
    ]

    result = builder.build(changes=changes, branch="main")

    assert set(_by_identity(result)) == {PYTHON_TARGET}


def test_python_reader_axis_is_off_for_a_creation() -> None:
    """A created peer names no Python target: it subscribes to no query group yet, so no reader reads it."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(python_attribute=True))
    changes = [MergeChange(node_id="peer-new", kind=PROFILE_PEER_KIND, action="created")]

    result = builder.build(changes=changes, branch="main")

    assert set(_by_identity(result)) == {
        (DISPLAY_LABEL, PROFILE_PEER_KIND, None),
        (HFID, PROFILE_PEER_KIND, None),
    }


def test_python_owner_axis_covers_a_created_node() -> None:
    """A created node holding the attribute is the one Python target a creation does name."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(python_attribute=True))
    changes = [MergeChange(node_id="node-new", kind=PROFILE_NODE_KIND, action="created")]

    result = builder.build(changes=changes, branch="main")

    assert PYTHON_TARGET in set(_by_identity(result))


def test_python_family_skips_a_deletion() -> None:
    """A deleted peer names no Python target, matching the per-node reader trigger that ignores deletes."""
    builder = CoalescedRecomputeBuilder(schema_branch=_profile_schema_branch(python_attribute=True))
    changes = [MergeChange(node_id="peer-gone", kind=PROFILE_PEER_KIND, action="deleted")]

    result = builder.build(changes=changes, branch="main")

    assert set(_by_identity(result)) == {
        (COMPUTED_ATTRIBUTE, PROFILE_NODE_KIND, "summary"),
        (DISPLAY_LABEL, PROFILE_NODE_KIND, None),
    }
