"""Narrowing of a merge or rebase change set to the affected Python computed attributes.

The resolver reads nothing by itself: the read-set index and the query-group subscribers arrive
through two injected sources, so these are unit tests over in-memory data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core.merge.python_target_resolution import IndexedPythonTargetResolver, PythonAttributeReadSet
from infrahub.core.merge.recompute_coalescing import (
    PYTHON_COMPUTED_ATTRIBUTE,
    SELF_FILTER,
    MergeChange,
    ReaderLookup,
)
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from tests.adapters.python_target_sources import (
    FailingSubscriberSource,
    RecordingSubscriberSource,
    StaticPythonReadSetSource,
)

if TYPE_CHECKING:
    from infrahub.core.merge.python_target_resolution import PythonSubscriberSource
    from infrahub.core.merge.recompute_coalescing import AffectedTarget

BRANCH = "main"
DEVICE = "TestingDevice"
ROUTER = "TestingRouter"
SITE = "TestingSite"
OWNER = "TestingOwner"

# Reads its own name and the name of the site it belongs to.
SUMMARY = PythonAttributeReadSet(
    kind=DEVICE,
    attribute_name="summary",
    read_set=TransformReadSet(
        read_kinds=frozenset({DEVICE, SITE}),
        read_fields={DEVICE: frozenset({"name"}), SITE: frozenset({"name"})},
    ),
)
# Reads its own description only.
LABEL = PythonAttributeReadSet(
    kind=DEVICE,
    attribute_name="label",
    read_set=TransformReadSet(read_kinds=frozenset({DEVICE}), read_fields={DEVICE: frozenset({"description"})}),
)
# Reads the site through a derived field, so that one kind is imprecise while the owner kind and
# the third kind keep their field filter.
TAG = PythonAttributeReadSet(
    kind=ROUTER,
    attribute_name="tag",
    read_set=TransformReadSet(
        read_kinds=frozenset({ROUTER, SITE, OWNER}),
        read_fields={ROUTER: frozenset({"name"}), OWNER: frozenset({"name"})},
        imprecise_kinds=frozenset({SITE}),
    ),
)
# The transform query could not be analyzed at all.
UNKNOWN = PythonAttributeReadSet(kind=OWNER, attribute_name="digest", read_set=TransformReadSet.imprecise())
# Reads the device name, but its query root is not pinned to one object, so query-group
# membership cannot name its readers.
UNPINNED = PythonAttributeReadSet(
    kind=OWNER,
    attribute_name="roster",
    read_set=TransformReadSet(read_kinds=frozenset({DEVICE}), read_fields={DEVICE: frozenset({"name"})}),
    pinned=False,
)


def _resolver(
    *,
    read_sets: list[PythonAttributeReadSet],
    subscriber_source: PythonSubscriberSource,
    refresh_updated_nodes: bool = False,
) -> IndexedPythonTargetResolver:
    return IndexedPythonTargetResolver(
        read_set_source=StaticPythonReadSetSource(read_sets=read_sets),
        subscriber_source=subscriber_source,
        refresh_updated_nodes=refresh_updated_nodes,
    )


def _identities(targets: list[AffectedTarget]) -> list[tuple[str, str | None]]:
    return [(target.target_kind, target.attribute_name) for target in targets]


def _ids(target: AffectedTarget) -> frozenset[str]:
    return frozenset(node_id for lookup in target.reader_lookups for node_id in lookup.source_node_ids)


async def test_created_nodes_are_their_own_targets() -> None:
    """A created node is in no query group yet, so it is reachable only as itself."""
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[SUMMARY, LABEL, TAG], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id="d1", kind=DEVICE, action="created"),
            MergeChange(node_id="d2", kind=DEVICE, action="created"),
        ],
    )

    assert _identities(targets) == [(DEVICE, "label"), (DEVICE, "summary")]
    for target in targets:
        assert target.family == PYTHON_COMPUTED_ATTRIBUTE
        assert target.precise is True
        assert target.whole_kind is False
        assert target.reader_lookups == frozenset(
            {ReaderLookup(source_kind=DEVICE, filter_key=SELF_FILTER, source_node_ids=frozenset({"d1", "d2"}))}
        )
    assert subscribers.calls == []


async def test_a_deleted_node_of_the_target_kind_is_not_its_own_target() -> None:
    """Self-targeting applies to an update, never to a deletion: the node has no value left.

    Its readers still come from the lookup, so only the deleted node itself drops out.
    """
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=subscribers)

    targets = await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="d1", kind=DEVICE, action="deleted")])

    assert subscribers.calls == [("d1",)]
    assert targets == []


async def test_an_update_selects_the_readers_of_the_changed_field_in_one_lookup() -> None:
    """Two changed sites resolve their readers with a single union lookup, not one per node."""
    subscribers = RecordingSubscriberSource(
        subscribers={"s1": [("d1", DEVICE), ("r1", ROUTER)], "s2": [("d2", DEVICE), ("d1", DEVICE)]}
    )
    resolver = _resolver(read_sets=[SUMMARY, LABEL, TAG], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"})),
            MergeChange(node_id="s2", kind=SITE, action="updated", changed_fields=frozenset({"name"})),
        ],
    )

    assert subscribers.calls == [("s1", "s2")]
    by_identity = dict(zip(_identities(targets), targets, strict=True))
    assert set(by_identity) == {(DEVICE, "summary"), (ROUTER, "tag")}
    summary, tag = by_identity[DEVICE, "summary"], by_identity[ROUTER, "tag"]
    # The subscriber index reports a node once per matching group; the duplicate collapses.
    assert _ids(summary) == frozenset({"d1", "d2"})
    assert summary.precise is True
    # The site is read through a derived field, so the site change is a deliberate over-selection.
    assert _ids(tag) == frozenset({"r1"})
    assert tag.precise is False


async def test_an_update_on_an_unread_field_selects_nothing() -> None:
    subscribers = RecordingSubscriberSource(subscribers={"d1": [("d1", DEVICE)]})
    resolver = _resolver(read_sets=[SUMMARY, LABEL, TAG], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"location"}))],
    )

    assert targets == []
    assert subscribers.calls == []


async def test_a_derived_read_on_one_kind_keeps_the_field_filter_of_the_others() -> None:
    """The imprecision of a derived read is held against its own kind, never against the read set.

    Collapsing the whole read set would disable the field filter for every kind the query reads,
    and a chained level would then select nodes the change cannot affect.
    """
    subscribers = RecordingSubscriberSource(subscribers={"o1": [("r1", ROUTER)]})
    resolver = _resolver(read_sets=[TAG], subscriber_source=subscribers)

    unread = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="o1", kind=OWNER, action="updated", changed_fields=frozenset({"description"}))],
    )
    read = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="o1", kind=OWNER, action="updated", changed_fields=frozenset({"name"}))],
    )

    assert unread == []
    assert _identities(read) == [(ROUTER, "tag")]
    assert _ids(read[0]) == frozenset({"r1"})
    assert read[0].precise is True


async def test_a_change_to_an_imprecise_kind_selects_on_any_field() -> None:
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("r1", ROUTER)]})
    resolver = _resolver(read_sets=[TAG], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"description"}))],
    )

    assert _identities(targets) == [(ROUTER, "tag")]
    assert _ids(targets[0]) == frozenset({"r1"})
    assert targets[0].precise is False


async def test_an_undeterminable_read_set_widens_to_the_whole_kind() -> None:
    """An attribute whose query could not be analyzed recomputes its kind rather than nothing."""
    subscribers = RecordingSubscriberSource(subscribers={"d1": [("o1", OWNER)]})
    resolver = _resolver(read_sets=[UNKNOWN], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"name"}))],
    )

    assert _identities(targets) == [(OWNER, "digest")]
    assert targets[0].whole_kind is True
    assert targets[0].precise is False
    assert targets[0].reader_lookups == frozenset()
    assert subscribers.calls == []


async def test_a_failing_reader_lookup_widens_instead_of_skipping() -> None:
    subscribers = FailingSubscriberSource()
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"}))],
    )

    assert subscribers.calls == [("s1",)]
    assert _identities(targets) == [(DEVICE, "summary")]
    assert targets[0].whole_kind is True
    assert targets[0].precise is False
    assert targets[0].reader_lookups == frozenset()


async def test_an_unscoped_update_selects_on_the_kind_alone() -> None:
    """Without changed fields there is nothing to filter on, so every reader of the kind counts."""
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE), ("r1", ROUTER)]})
    resolver = _resolver(read_sets=[SUMMARY, LABEL, TAG], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH, changes=[MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset())]
    )

    by_identity = dict(zip(_identities(targets), targets, strict=True))
    assert set(by_identity) == {(DEVICE, "summary"), (ROUTER, "tag")}
    summary, tag = by_identity[DEVICE, "summary"], by_identity[ROUTER, "tag"]
    assert _ids(summary) == frozenset({"d1"})
    assert _ids(tag) == frozenset({"r1"})
    assert summary.precise is False
    assert tag.precise is False


async def test_deleted_nodes_select_their_readers() -> None:
    """Every field the query read is gone with the node, so dropping the field filter is exact."""
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE)]})
    resolver = _resolver(read_sets=[SUMMARY, LABEL], subscriber_source=subscribers)

    targets = await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="s1", kind=SITE, action="deleted")])

    assert _identities(targets) == [(DEVICE, "summary")]
    assert _ids(targets[0]) == frozenset({"d1"})
    assert targets[0].precise is True
    assert targets[0].whole_kind is False


async def test_attributes_selected_by_different_changes_do_not_share_subscribers() -> None:
    """Keying the memo on the id set is what keeps one attribute out of another's readers."""
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE)], "d9": [("d9", DEVICE)]})
    resolver = _resolver(read_sets=[SUMMARY, LABEL], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"})),
            MergeChange(node_id="d9", kind=DEVICE, action="updated", changed_fields=frozenset({"description"})),
        ],
    )

    assert sorted(subscribers.calls) == [("d9",), ("s1",)]
    by_identity = dict(zip(_identities(targets), targets, strict=True))
    assert _ids(by_identity[DEVICE, "summary"]) == frozenset({"d1"})
    assert _ids(by_identity[DEVICE, "label"]) == frozenset({"d9"})


async def test_an_updated_node_of_the_target_kind_is_its_own_target() -> None:
    """The reverse lookup reaches a node only through the group its last compute subscribed it to.

    A node that never computed is in no group, so relying on the lookup alone leaves it stale.
    """
    # No subscribers at all: this node belongs to no query group.
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[LABEL], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"description"}))],
    )

    assert _identities(targets) == [(DEVICE, "label")]
    assert _ids(targets[0]) == frozenset({"d1"})


async def test_a_replayed_update_refreshes_the_node_itself_whichever_fields_changed() -> None:
    """A rebase moves the base under every value the updated node derived, including one it reads no changed field for.

    Only the node itself is refreshed this way: the readers of another kind keep the field filter.
    """
    subscribers = RecordingSubscriberSource(subscribers={"d1": [("d9", DEVICE)], "s1": [("d9", DEVICE)]})
    resolver = _resolver(read_sets=[SUMMARY, LABEL], subscriber_source=subscribers, refresh_updated_nodes=True)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"location"})),
            MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"location"})),
        ],
    )

    assert _identities(targets) == [(DEVICE, "label"), (DEVICE, "summary")]
    for target in targets:
        assert target.precise is True
        assert target.whole_kind is False
        assert target.reader_lookups == frozenset(
            {ReaderLookup(source_kind=DEVICE, filter_key=SELF_FILTER, source_node_ids=frozenset({"d1"}))}
        )
    assert subscribers.calls == []


async def test_a_deleted_id_is_resolved_apart_from_the_live_ids() -> None:
    """A deleted id empties the lookup it shares, so it must not travel with the live ids."""
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE)]}, empties_lookup={"s2"})
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"})),
            MergeChange(node_id="s2", kind=SITE, action="deleted"),
        ],
    )

    assert sorted(subscribers.calls) == [("s1",), ("s2",)]
    assert _identities(targets) == [(DEVICE, "summary")]
    assert _ids(targets[0]) == frozenset({"d1"})


async def test_a_change_with_no_subscribed_reader_adds_no_target() -> None:
    """An empty lookup is an answer, not a failure, so it must not produce an id-less submission."""
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"}))],
    )

    assert subscribers.calls == [("s1",)]
    assert targets == []


async def test_an_unknown_change_action_is_refused() -> None:
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=RecordingSubscriberSource(subscribers={}))

    with pytest.raises(ValueError, match=r"^Unknown change action: 'moved'$"):
        await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="s1", kind=SITE, action="moved")])


async def test_every_lookup_of_a_pass_runs_on_the_branch_it_was_asked_for() -> None:
    """Every lookup carries the branch it was asked for, and the memo is keyed on it.

    A rebase recomputes on the user branch while a merge recomputes on the destination, and a
    lookup sent to the wrong branch answers with that branch's query groups.
    """
    subscribers = RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE)]})
    resolver = _resolver(read_sets=[SUMMARY], subscriber_source=subscribers)
    change = MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"}))

    await resolver.resolve(branch=BRANCH, changes=[change])
    await resolver.resolve(branch="user-branch", changes=[change])

    assert subscribers.branches == [BRANCH, "user-branch"]


async def test_the_read_set_index_is_fetched_once_per_pass() -> None:
    read_set_source = StaticPythonReadSetSource(read_sets=[SUMMARY])
    resolver = IndexedPythonTargetResolver(
        read_set_source=read_set_source,
        subscriber_source=RecordingSubscriberSource(subscribers={"s1": [("d1", DEVICE)]}),
    )

    change = MergeChange(node_id="s1", kind=SITE, action="updated", changed_fields=frozenset({"name"}))
    await resolver.resolve(branch=BRANCH, changes=[change])
    await resolver.resolve(branch=BRANCH, changes=[change])

    assert read_set_source.calls == [BRANCH]


async def test_an_unpinned_query_widens_on_an_update_to_a_field_it_reads() -> None:
    """Group membership records only what the last run read, so it cannot name the next readers."""
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNPINNED], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"name"}))],
    )

    assert _identities(targets) == [(OWNER, "roster")]
    assert targets[0].whole_kind is True


async def test_a_created_node_widens_an_unpinned_query() -> None:
    """A created node enters the result set of an unpinned query without touching its members."""
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNPINNED], subscriber_source=subscribers)

    targets = await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="d1", kind=DEVICE, action="created")])

    assert _identities(targets) == [(OWNER, "roster")]
    assert targets[0].whole_kind is True


async def test_a_created_node_widens_an_undeterminable_read_set() -> None:
    """What an unanalyzable query reads is unknown, so a creation can reach it like any change."""
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNKNOWN], subscriber_source=subscribers)

    targets = await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="d1", kind=DEVICE, action="created")])

    assert _identities(targets) == [(OWNER, "digest")]
    assert targets[0].whole_kind is True


async def test_an_unpinned_query_widens_on_a_field_it_reads_without_selecting() -> None:
    """A filter argument never reaches the read set, so an unread field can still move members.

    An unpinned query filtering on one field and selecting another takes a node into or out of its
    result when that filter field changes, and no field filter here can see it.
    """
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNPINNED], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[MergeChange(node_id="d1", kind=DEVICE, action="updated", changed_fields=frozenset({"colour"}))],
    )

    assert _identities(targets) == [(OWNER, "roster")]
    assert targets[0].whole_kind is True
    assert targets[0].precise is False
    assert subscribers.calls == []


async def test_a_created_node_of_an_unpinned_attribute_kind_is_its_own_target() -> None:
    """An unpinned query that never reads the owner kind still leaves the new node to compute.

    Nothing moves for the members already in the result, since the query does not read this kind,
    so the created node is the exact target and no lookup is needed.
    """
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNPINNED], subscriber_source=subscribers)

    targets = await resolver.resolve(branch=BRANCH, changes=[MergeChange(node_id="o1", kind=OWNER, action="created")])

    assert _identities(targets) == [(OWNER, "roster")]
    assert targets[0].whole_kind is False
    assert targets[0].precise is True
    assert targets[0].reader_lookups == frozenset(
        {ReaderLookup(source_kind=OWNER, filter_key=SELF_FILTER, source_node_ids=frozenset({"o1"}))}
    )
    assert subscribers.calls == []


@dataclass
class UnreadKindCase:
    name: str
    kind: str
    node_id: str


@pytest.mark.parametrize(
    "case",
    [
        UnreadKindCase(name="a_kind_the_query_never_reads", kind=SITE, node_id="s1"),
        UnreadKindCase(name="the_kind_the_attribute_lives_on", kind=OWNER, node_id="o1"),
    ],
    ids=lambda case: case.name,
)
async def test_an_unpinned_query_ignores_an_update_to_a_kind_it_never_reads(case: UnreadKindCase) -> None:
    """Widening on any read kind must not become widening on every merge.

    The attribute's own kind is one of those unread kinds here, and an update to it moves nothing
    the query reads, so it selects nothing either.
    """
    subscribers = RecordingSubscriberSource(subscribers={})
    resolver = _resolver(read_sets=[UNPINNED], subscriber_source=subscribers)

    targets = await resolver.resolve(
        branch=BRANCH,
        changes=[
            MergeChange(node_id=case.node_id, kind=case.kind, action="updated", changed_fields=frozenset({"name"}))
        ],
    )

    assert targets == []
    assert subscribers.calls == []
