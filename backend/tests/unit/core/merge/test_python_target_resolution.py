"""Narrowing of the Python targets of a coalesced recompute."""

from __future__ import annotations

from dataclasses import replace

import pytest
from structlog.testing import capture_logs

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
from infrahub.core.timestamp import Timestamp
from tests.helpers.merge_recompute.resolver import (
    FailingReadFieldIndex,
    FailingSubscriberLookup,
    LookupCall,
    RecordingReadFieldIndex,
    RecordingSubscriberLookup,
)

DELETED_AT = Timestamp("2026-01-01T00:00:00Z")

OWNER_KIND = "TestingTShirt"
PEER_KIND = "TestingColor"
ATTRIBUTE = "pitch"
KEY = (OWNER_KIND, ATTRIBUTE)


def _read_set(
    read_kinds: frozenset[str] | None = None,
    read_fields: dict[str, frozenset[str]] | None = None,
    depends_on_everything: bool = False,
) -> TransformReadSet:
    return TransformReadSet(
        read_kinds=frozenset({OWNER_KIND, PEER_KIND}) if read_kinds is None else read_kinds,
        read_fields={OWNER_KIND: frozenset({"name"}), PEER_KIND: frozenset({"description"})}
        if read_fields is None
        else read_fields,
        depends_on_everything=depends_on_everything,
    )


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


# An empty index is a meaningful case, so it must not be conflated with "not supplied".
_DEFAULT: dict[tuple[str, str], TransformReadSet] = {}


def _resolver(
    *,
    index: dict[tuple[str, str], TransformReadSet] | None = None,
    readers: dict[str, frozenset[str]] | None = None,
    readers_at: dict[str, frozenset[str]] | None = None,
    failing_index: bool = False,
    failing_lookup: bool = False,
) -> tuple[NarrowingPythonTargetResolver, RecordingSubscriberLookup | FailingSubscriberLookup]:
    resolved_index = {KEY: _read_set()} if index is None else index
    read_field_index = FailingReadFieldIndex() if failing_index else RecordingReadFieldIndex(index=resolved_index)
    lookup = (
        FailingSubscriberLookup()
        if failing_lookup
        else RecordingSubscriberLookup(readers=readers or {}, readers_at=readers_at)
    )
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
    assert lookup.calls == [LookupCall(node_ids=frozenset({"color-0", "color-1", "color-2"}), at=None)], (
        "one lookup over the union, not one per node"
    )


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
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=DELETED_AT
    )

    assert next(iter(_only(result).reader_lookups)).source_node_ids == frozenset({"shirt-1"})


async def test_a_deleted_peer_is_looked_up_before_it_went() -> None:
    """A deleted node's memberships are already closed, so its readers need the earlier time.

    Taking the whole set at that time instead would hide a membership the merge itself created,
    so the two halves are looked up separately and unioned.
    """
    resolver, lookup = _resolver(
        readers={OWNER_KIND: frozenset({"shirt-live"})},
        readers_at={OWNER_KIND: frozenset({"shirt-gone-reader"})},
    )
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"})),
        MergeChange(node_id="color-gone", kind=PEER_KIND, action=DELETED),
    ]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=DELETED_AT
    )

    assert next(iter(_only(result).reader_lookups)).source_node_ids == frozenset({"shirt-live", "shirt-gone-reader"})
    assert lookup.calls == [
        LookupCall(node_ids=frozenset({"color-1"}), at=None),
        LookupCall(node_ids=frozenset({"color-gone"}), at=DELETED_AT),
    ]


async def test_a_deletion_with_no_point_in_time_widens() -> None:
    """Without a time to look at, the readers of a deleted node cannot be found at all."""
    resolver, _ = _resolver(readers={OWNER_KIND: frozenset({"shirt-1"})})
    changes = [MergeChange(node_id="color-gone", kind=PEER_KIND, action=DELETED)]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert _only(result).whole_kind is True


async def test_a_change_on_the_owning_kind_is_also_a_reader_source() -> None:
    """A transform can read other nodes of the kind it belongs to, so its own kind is looked up too."""
    resolver, lookup = _resolver(readers={OWNER_KIND: frozenset({"shirt-2"})})
    changes = [MergeChange(node_id="shirt-1", kind=OWNER_KIND, action=UPDATED, changed_fields=frozenset({"name"}))]

    result = await resolver.resolve(
        coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None
    )

    assert next(iter(_only(result).reader_lookups)).source_node_ids == frozenset({"shirt-1", "shirt-2"})
    assert lookup.calls == [LookupCall(node_ids=frozenset({"shirt-1"}), at=None)]


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


async def test_the_selection_is_logged_with_a_node_count_per_pair() -> None:
    """A merge that recomputed too much has to be readable from the logs afterwards."""
    resolver, _ = _resolver(readers={OWNER_KIND: frozenset({"shirt-1", "shirt-2"})})
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    with capture_logs() as records:
        await resolver.resolve(coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None)

    selection = next(record for record in records if record["event"] == "COALESCED_PYTHON selected targets")
    assert selection["branch"] == "main"
    assert selection["considered"] == 1
    assert selection["selected"] == 1
    assert selection["widened"] == 0
    assert selection["targets"] == [f"{OWNER_KIND}.{ATTRIBUTE}=2"]


async def test_a_widening_is_logged_with_its_pair_and_reason() -> None:
    """FR-020 is checked against this: the pair and the why must both survive into the logs."""
    resolver, _ = _resolver(failing_lookup=True)
    changes = [
        MergeChange(node_id="color-1", kind=PEER_KIND, action=UPDATED, changed_fields=frozenset({"description"}))
    ]

    with capture_logs() as records:
        await resolver.resolve(coalesced=_coalesced(_python_target()), changes=changes, branch="main", deleted_at=None)

    widening = next(record for record in records if record["event"] == "COALESCED_PYTHON widened to whole kind")
    assert widening["kind"] == OWNER_KIND
    assert widening["attribute"] == ATTRIBUTE
    assert "subscriber lookup failed" in widening["reason"]

    selection = next(record for record in records if record["event"] == "COALESCED_PYTHON selected targets")
    assert selection["widened"] == 1
    assert selection["targets"] == [f"{OWNER_KIND}.{ATTRIBUTE}=whole-kind"]
