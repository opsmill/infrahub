"""Narrowing of the Python targets of a coalesced recompute."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

import pytest

from infrahub.core.merge.python_target_resolution import NarrowingPythonTargetResolver
from infrahub.core.merge.recompute_coalescing import (
    COMPUTED_ATTRIBUTE,
    CREATED,
    DELETED,
    PYTHON_ATTRIBUTE,
    UPDATED,
    AffectedTarget,
    CoalescedRecompute,
    MergeChange,
    ReaderLookup,
)
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from tests.helpers.merge_recompute.resolver import (
    FailingReadFieldIndex,
    FailingSubscriberLookup,
    RecordingReadFieldIndex,
    RecordingSubscriberLookup,
)

OWNER_KIND = "TestingTShirt"
PEER_KIND = "TestingColor"
ATTRIBUTE = "pitch"
KEY = (OWNER_KIND, ATTRIBUTE)


def _read_set(**kwargs: Any) -> TransformReadSet:
    defaults = {
        "read_kinds": frozenset({OWNER_KIND, PEER_KIND}),
        "read_fields": {OWNER_KIND: frozenset({"name"}), PEER_KIND: frozenset({"description"})},
    }
    return TransformReadSet(**{**defaults, **kwargs})


def _python_target() -> AffectedTarget:
    return AffectedTarget(
        family=PYTHON_ATTRIBUTE,
        target_kind=OWNER_KIND,
        attribute_name=ATTRIBUTE,
        reads_across_relationship=True,
        reader_lookups=frozenset(),
    )


def _coalesced(*targets: AffectedTarget) -> CoalescedRecompute:
    return CoalescedRecompute(branch="main", targets=frozenset(targets))


_DEFAULT = object()


def _resolver(
    *,
    index: dict[tuple[str, str], TransformReadSet] | object = _DEFAULT,
    readers: dict[str, frozenset[str]] | None = None,
    failing_index: bool = False,
    failing_lookup: bool = False,
) -> tuple[NarrowingPythonTargetResolver, RecordingSubscriberLookup | FailingSubscriberLookup]:
    # An empty index is a meaningful case, so it must not be conflated with "not supplied".
    resolved_index = {KEY: _read_set()} if index is _DEFAULT else index
    read_field_index = FailingReadFieldIndex() if failing_index else RecordingReadFieldIndex(index=resolved_index)
    lookup = FailingSubscriberLookup() if failing_lookup else RecordingSubscriberLookup(readers=readers or {})
    return NarrowingPythonTargetResolver(read_field_index=read_field_index, subscriber_lookup=lookup), lookup


def _only(result: CoalescedRecompute) -> AffectedTarget:
    targets = list(result.targets)
    assert len(targets) == 1
    return targets[0]


async def test_owner_change_on_a_read_field_selects_that_node() -> None:
    resolver, _ = _resolver()
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    target = _only(result)
    assert target.whole_kind is False
    assert target.precise is True
    assert target.reader_lookups == frozenset(
        {ReaderLookup(source_kind=OWNER_KIND, filter_key="ids", source_node_ids=frozenset({"shirt-1"}))}
    )


async def test_owner_change_on_an_unread_field_selects_nothing() -> None:
    """A field the query does not read cannot change the value.

    The per-node automation already filters on the read fields, so dropping that filter
    would recompute more nodes than the path being replaced, not fewer.
    """
    resolver, _ = _resolver()
    changes = [
        MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert result.targets == frozenset()


async def test_peer_change_resolves_its_readers_in_one_lookup() -> None:
    resolver, lookup = _resolver(readers={OWNER_KIND: frozenset({"shirt-1", "shirt-2"})})
    changes = [
        MergeChange(node_id=f"color-{index}", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
        for index in range(3)
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    target = _only(result)
    assert next(iter(target.reader_lookups)).source_node_ids == frozenset({"shirt-1", "shirt-2"})
    assert lookup.calls == [frozenset({"color-0", "color-1", "color-2"})], "one lookup over the union, not one per node"


async def test_lookup_that_finds_nothing_drops_the_target() -> None:
    resolver, _ = _resolver(readers={})
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert result.targets == frozenset(), "looked and found none means nothing to do"


async def test_lookup_that_fails_widens_rather_than_dropping() -> None:
    resolver, _ = _resolver(failing_lookup=True)
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    target = _only(result)
    assert target.whole_kind is True, "could not look must never collapse into found none"
    assert target.precise is False


async def test_imprecise_read_set_widens() -> None:
    resolver, _ = _resolver(index={KEY: _read_set(depends_on_everything=True)})
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert _only(result).whole_kind is True


async def test_missing_read_set_widens() -> None:
    resolver, _ = _resolver(index={})
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert _only(result).whole_kind is True


async def test_index_failure_widens_every_python_target_and_does_not_raise() -> None:
    resolver, _ = _resolver(failing_index=True)
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert _only(result).whole_kind is True


async def test_other_families_pass_through_untouched_when_the_lookup_fails() -> None:
    """An escaping error would drop the recompute of all four families, not just this one."""
    jinja = AffectedTarget(
        family=COMPUTED_ATTRIBUTE,
        target_kind=OWNER_KIND,
        attribute_name="summary",
        reads_across_relationship=False,
        reader_lookups=frozenset(
            {ReaderLookup(source_kind=OWNER_KIND, filter_key="ids", source_node_ids=frozenset({"shirt-9"}))}
        ),
    )
    resolver, _ = _resolver(failing_lookup=True)
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target(), jinja), changes=changes, branch="main", deleted_at=None
    )

    assert jinja in result.targets


async def test_no_python_target_does_no_io_at_all() -> None:
    resolver, lookup = _resolver(failing_index=True)
    jinja = AffectedTarget(
        family=COMPUTED_ATTRIBUTE,
        target_kind=OWNER_KIND,
        attribute_name="summary",
        reads_across_relationship=False,
        reader_lookups=frozenset(),
    )

    result = await resolver.resolve(coalesced=_coalesced(jinja), changes=[], branch="main", deleted_at=None)

    assert result.targets == frozenset({jinja})
    assert lookup.calls == []


async def test_update_reporting_no_field_selects_and_stays_imprecise() -> None:
    """An update with no field list may have touched anything the query reads.

    The builder already marks that shape imprecise, and narrowing it must not claim a precision
    the change set does not have.
    """
    resolver, _ = _resolver()
    imprecise = replace(_python_target(), precise=False)
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset())]

    result = await resolver.resolve(coalesced=_coalesced(imprecise), changes=changes, branch="main", deleted_at=None)

    target = _only(result)
    assert next(iter(target.reader_lookups)).source_node_ids == frozenset({"shirt-1"})
    assert target.precise is False


async def test_deleted_owner_is_not_a_target() -> None:
    """A deleted node cannot be recomputed, so only the surviving one is scheduled."""
    resolver, _ = _resolver()
    changes = [
        MergeChange(node_id="shirt-gone", kind=OWNER_KIND, action=DELETED),
        MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"})),
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert next(iter(_only(result).reader_lookups)).source_node_ids == frozenset({"shirt-1"})


async def test_a_change_on_the_owning_kind_is_also_a_reader_source() -> None:
    """A transform can read other nodes of the kind it belongs to, so its own kind is looked up too."""
    resolver, lookup = _resolver(readers={OWNER_KIND: frozenset({"shirt-2"})})
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert next(iter(_only(result).reader_lookups)).source_node_ids == frozenset({"shirt-1", "shirt-2"})
    assert lookup.calls == [frozenset({"shirt-1"})]


@pytest.mark.parametrize(
    ("action", "expected"),
    [(CREATED, True), (DELETED, True), (UPDATED, False)],
)
async def test_kind_level_dependency_selects_on_appearance_not_on_field_edits(action: str, expected: bool) -> None:
    """A kind the query reaches but reads no field from is a kind-level dependency.

    Its instances appearing or disappearing changes the result set; editing a field on one
    cannot, because no field of it is read.
    """
    read_set = _read_set(read_fields={OWNER_KIND: frozenset({"name"})})
    resolver, _ = _resolver(index={KEY: read_set}, readers={OWNER_KIND: frozenset({"shirt-1"})})
    changes = [MergeChange(node_id="color-1", kind=PEER_KIND, action=action, changed_fields=frozenset({"anything"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert (result.targets != frozenset()) is expected
