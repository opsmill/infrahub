from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from infrahub.core.changelog.enrichment import NodeLabelLoader, NodeLabels
from infrahub.core.changelog.hfid_resolver import ChangelogHfidResolver, _hfid_from_diff
from infrahub.core.changelog.models import (
    AttributeChangelog,
    NodeChangelog,
    RelationshipCardinalityManyChangelog,
    RelationshipCardinalityOneChangelog,
    RelationshipPeerChangelog,
)
from infrahub.core.constants import DiffAction
from infrahub.core.constants.schema import HFID_ATTRIBUTE_NAME


class RecordingReader:
    """Test double for NodeLabelReader: returns preset HFIDs and records the IDs of each load in order."""

    def __init__(self, hfids: dict[str, list[str] | None]) -> None:
        self._hfids = hfids
        self.hfid_calls: list[list[str]] = []

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        raise AssertionError("the resolver only loads HFIDs")

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        self.hfid_calls.append(node_ids)
        return {node_id: self._hfids[node_id] for node_id in node_ids if node_id in self._hfids}


class FailingReader:
    """Test double for NodeLabelReader that always raises, standing in for a read failure."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        raise RuntimeError("label backend unavailable")

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        raise RuntimeError("label backend unavailable")


def _resolver(hfids: dict[str, list[str] | None]) -> tuple[ChangelogHfidResolver, RecordingReader]:
    reader = RecordingReader(hfids)
    return ChangelogHfidResolver(label_loader=NodeLabelLoader(reader=reader)), reader


def _node(node_id: str, *, hfid_attribute_value: str | None = None) -> NodeChangelog:
    changelog = NodeChangelog(node_id=node_id, node_kind="TestCar", display_label="label")
    if hfid_attribute_value is not None:
        changelog.attributes[HFID_ATTRIBUTE_NAME] = AttributeChangelog(
            name=HFID_ATTRIBUTE_NAME, kind="Text", value=hfid_attribute_value
        )
    return changelog


def _hfid_attribute(*, value: Any = None, value_previous: Any = None) -> AttributeChangelog:
    return AttributeChangelog(name=HFID_ATTRIBUTE_NAME, kind="Text", value=value, value_previous=value_previous)


@dataclass
class HfidFromDiffCase:
    name: str
    attribute: AttributeChangelog
    expected: list[str] | None


HFID_FROM_DIFF_CASES = [
    HfidFromDiffCase(
        name="json_list_value_is_parsed",
        attribute=_hfid_attribute(value='["Volvo", "5"]'),
        expected=["Volvo", "5"],
    ),
    HfidFromDiffCase(
        name="previous_value_is_used_when_current_is_absent",
        attribute=_hfid_attribute(value=None, value_previous='["Old"]'),
        expected=["Old"],
    ),
    HfidFromDiffCase(
        name="non_string_value_yields_none",
        attribute=_hfid_attribute(value=["Volvo"]),
        expected=None,
    ),
    HfidFromDiffCase(
        name="invalid_json_yields_none",
        attribute=_hfid_attribute(value="not-json"),
        expected=None,
    ),
    HfidFromDiffCase(
        name="json_that_is_not_a_list_yields_none",
        attribute=_hfid_attribute(value='"Volvo"'),
        expected=None,
    ),
]


@pytest.mark.parametrize("case", HFID_FROM_DIFF_CASES, ids=lambda case: case.name)
def test_hfid_from_diff(case: HfidFromDiffCase) -> None:
    node = NodeChangelog(node_id="n1", node_kind="TestCar", display_label="label")
    node.add_attribute(attribute=case.attribute)

    assert _hfid_from_diff(node) == case.expected


def test_hfid_from_diff_without_attribute_yields_none() -> None:
    node = NodeChangelog(node_id="n1", node_kind="TestCar", display_label="label")

    assert _hfid_from_diff(node) is None


async def test_enrich_sets_node_hfid_from_loaded_batch() -> None:
    resolver, reader = _resolver({"n1": ["Volvo", "5"]})
    node = _node("n1")

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1"])

    assert node.hfid == ["Volvo", "5"]
    assert reader.hfid_calls == [["n1"]]


async def test_enrich_removed_node_missing_from_batch_falls_back_to_diff() -> None:
    resolver, reader = _resolver({})
    node = _node("n1", hfid_attribute_value='["Gone"]')

    await resolver.enrich(changelogs=[(DiffAction.REMOVED, node)], resolvable_ids=["n1"])

    assert node.hfid == ["Gone"]
    # The fallback reads the diff, not a second load: the batch is the only read.
    assert reader.hfid_calls == [["n1"]]


async def test_enrich_removed_node_present_in_batch_keeps_loaded_hfid() -> None:
    resolver, reader = _resolver({"n1": ["Fresh"]})
    node = _node("n1", hfid_attribute_value='["Stale"]')

    await resolver.enrich(changelogs=[(DiffAction.REMOVED, node)], resolvable_ids=["n1"])

    assert node.hfid == ["Fresh"]
    assert reader.hfid_calls == [["n1"]]


async def test_enrich_non_removed_node_missing_from_batch_stays_none() -> None:
    resolver, reader = _resolver({})
    node = _node("n1", hfid_attribute_value='["Ignored"]')

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1"])

    assert node.hfid is None
    assert reader.hfid_calls == [["n1"]]


async def test_enrich_internal_peer_resolved_from_batch_without_extra_load() -> None:
    resolver, reader = _resolver({"n1": ["A"], "n2": ["B"]})
    node = _node("n1")
    node.relationships["owner"] = RelationshipCardinalityOneChangelog(name="owner", peer_id="n2")

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1", "n2"])

    owner = node.relationships["owner"]
    assert isinstance(owner, RelationshipCardinalityOneChangelog)
    assert owner.peer_hfid == ["B"]
    assert reader.hfid_calls == [["n1", "n2"]]


async def test_enrich_external_peer_loaded_separately() -> None:
    resolver, reader = _resolver({"n1": ["A"], "ext": ["E"]})
    node = _node("n1")
    node.relationships["owner"] = RelationshipCardinalityOneChangelog(name="owner", peer_id="ext")

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1"])

    owner = node.relationships["owner"]
    assert isinstance(owner, RelationshipCardinalityOneChangelog)
    assert owner.peer_hfid == ["E"]
    assert reader.hfid_calls == [["n1"], ["ext"]]


async def test_enrich_peer_in_batch_with_no_hfid_is_not_reloaded() -> None:
    resolver, reader = _resolver({"n1": ["A"], "n2": None})
    node = _node("n1")
    node.relationships["members"] = RelationshipCardinalityManyChangelog(
        name="members",
        peers=[RelationshipPeerChangelog(peer_id="n2", peer_kind="TestCar", peer_status=DiffAction.ADDED)],
    )

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1", "n2"])

    members = node.relationships["members"]
    assert isinstance(members, RelationshipCardinalityManyChangelog)
    assert members.peers[0].peer_hfid is None
    assert reader.hfid_calls == [["n1", "n2"]]


async def test_enrich_degrades_when_reader_fails() -> None:
    resolver = ChangelogHfidResolver(label_loader=NodeLabelLoader(reader=FailingReader()))
    node = _node("n1")
    node.relationships["owner"] = RelationshipCardinalityOneChangelog(name="owner", peer_id="ext")

    await resolver.enrich(changelogs=[(DiffAction.UPDATED, node)], resolvable_ids=["n1"])

    owner = node.relationships["owner"]
    assert isinstance(owner, RelationshipCardinalityOneChangelog)
    assert node.hfid is None
    assert owner.peer_hfid is None
