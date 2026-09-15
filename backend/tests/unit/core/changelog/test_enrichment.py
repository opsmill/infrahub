from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.branch import Branch
from infrahub.core.changelog.enrichment import (
    HFID_FIELDS,
    LABEL_FIELDS,
    DbNodeLabelReader,
    NodeLabelLoader,
    NodeLabels,
)
from infrahub.database import InfrahubDatabase

if TYPE_CHECKING:
    import pytest


class RecordingReader:
    """Test double for NodeLabelReader: returns preset labels and records each method's IDs separately."""

    def __init__(self, labels: dict[str, NodeLabels]) -> None:
        self._labels = labels
        self.label_calls: list[list[str]] = []
        self.hfid_calls: list[list[str]] = []

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        self.label_calls.append(node_ids)
        return {node_id: self._labels[node_id] for node_id in node_ids if node_id in self._labels}

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        self.hfid_calls.append(node_ids)
        return {node_id: self._labels[node_id].hfid for node_id in node_ids if node_id in self._labels}


class FailingReader:
    """Test double for NodeLabelReader that always raises, standing in for a read failure."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        raise RuntimeError("label backend unavailable")

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        raise RuntimeError("label backend unavailable")


async def test_load_labels_deduplicates_sorts_and_drops_empty_ids() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"]), "b": NodeLabels("B", ["b"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["b", "", "a", "a", "b"])

    assert reader.label_calls == [["a", "b"]]
    assert result == {"a": NodeLabels("A", ["a"]), "b": NodeLabels("B", ["b"])}


async def test_load_labels_on_empty_input_never_reads() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["", ""])

    assert result == {}
    assert reader.label_calls == []


async def test_load_labels_holds_only_the_nodes_the_reader_found() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["a", "missing"])

    assert result == {"a": NodeLabels("A", ["a"])}


async def test_load_hfids_projects_only_the_hfid() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a", "x"]), "b": NodeLabels("B", None)})

    result = await NodeLabelLoader(reader=reader).load_hfids(["a", "b"])

    assert result == {"a": ["a", "x"], "b": None}
    assert reader.hfid_calls == [["a", "b"]]
    assert reader.label_calls == []


async def test_load_labels_degrades_to_empty_when_the_reader_fails() -> None:
    result = await NodeLabelLoader(reader=FailingReader()).load_labels(["a", "b"])

    assert result == {}


async def test_load_hfids_degrades_to_empty_when_the_reader_fails() -> None:
    result = await NodeLabelLoader(reader=FailingReader()).load_hfids(["a", "b"])

    assert result == {}


class UnusableDatabase(InfrahubDatabase):
    """Placeholder for the database the reader forwards to its collaborators and never touches itself.

    Skipping the base __init__ leaves the object without a driver, so any accidental database call
    fails loudly with AttributeError.
    """

    def __init__(self) -> None:
        pass


@dataclass
class FakeNode:
    """Test double for a loaded node: fixed labels, each flagged as stored or not."""

    display_label: str
    hfid: list[str] | None
    label_stored: bool = True
    hfid_stored: bool = True

    def display_label_needs_read(self) -> bool:
        return not self.label_stored

    def hfid_needs_read(self) -> bool:
        return not self.hfid_stored

    async def get_display_label(self, db: InfrahubDatabase) -> str:
        return self.display_label

    async def get_hfid(self, db: InfrahubDatabase) -> list[str] | None:
        return self.hfid


@dataclass
class RecordingNodeLoader:
    """Test double for the node loader: serves one node set for restricted reads and one for whole reads.

    Each call's requested IDs and fields are recorded in order.
    """

    restricted: dict[str, FakeNode]
    whole: dict[str, FakeNode]
    calls: list[tuple[list[str], dict[str, Any] | None]] = field(default_factory=list)

    async def __call__(
        self, *, db: InfrahubDatabase, ids: list[str], branch: Branch, fields: dict[str, Any] | None
    ) -> dict[str, FakeNode]:
        self.calls.append((ids, fields))
        source = self.whole if fields is None else self.restricted
        return {node_id: source[node_id] for node_id in ids if node_id in source}


def _reader(loader: RecordingNodeLoader) -> DbNodeLabelReader:
    return DbNodeLabelReader(db=UnusableDatabase(), branch=Branch(name="main"), node_loader=loader)


async def test_reader_loads_labels_with_only_the_label_fields() -> None:
    loader = RecordingNodeLoader(restricted={"a": FakeNode("A", ["a"])}, whole={})

    labels = await _reader(loader).load_labels(["a"])

    assert labels == {"a": NodeLabels(display_label="A", hfid=["a"])}
    assert loader.calls == [(["a"], LABEL_FIELDS)]


async def test_reader_loads_hfids_with_only_the_hfid_field() -> None:
    loader = RecordingNodeLoader(restricted={"a": FakeNode("A", ["a"])}, whole={})

    hfids = await _reader(loader).load_hfids(["a"])

    assert hfids == {"a": ["a"]}
    assert loader.calls == [(["a"], HFID_FIELDS)]


async def test_reader_reloads_whole_only_the_nodes_whose_labels_are_not_stored() -> None:
    loader = RecordingNodeLoader(
        restricted={
            "stored": FakeNode("Stored", ["s"]),
            "no_label": FakeNode("", None, label_stored=False),
            "no_hfid": FakeNode("Partial", None, hfid_stored=False),
        },
        whole={"no_label": FakeNode("Computed label", ["c"]), "no_hfid": FakeNode("Partial", ["computed"])},
    )

    labels = await _reader(loader).load_labels(["stored", "no_label", "no_hfid"])

    assert labels == {
        "stored": NodeLabels(display_label="Stored", hfid=["s"]),
        "no_label": NodeLabels(display_label="Computed label", hfid=["c"]),
        "no_hfid": NodeLabels(display_label="Partial", hfid=["computed"]),
    }
    assert loader.calls == [(["stored", "no_label", "no_hfid"], LABEL_FIELDS), (["no_label", "no_hfid"], None)]


async def test_reader_reloads_for_hfids_only_when_the_hfid_is_not_stored() -> None:
    loader = RecordingNodeLoader(
        restricted={
            "no_label": FakeNode("", ["s"], label_stored=False),
            "no_hfid": FakeNode("P", None, hfid_stored=False),
        },
        whole={"no_hfid": FakeNode("P", ["computed"])},
    )

    hfids = await _reader(loader).load_hfids(["no_label", "no_hfid"])

    # A missing display label is irrelevant to an HFID read, so that node is not reloaded.
    assert hfids == {"no_label": ["s"], "no_hfid": ["computed"]}
    assert loader.calls == [(["no_label", "no_hfid"], HFID_FIELDS), (["no_hfid"], None)]


async def test_reader_pages_both_the_restricted_read_and_the_reload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config.SETTINGS.database, "query_size_limit", 2)
    ids = ["n1", "n2", "n3"]
    loader = RecordingNodeLoader(
        restricted={node_id: FakeNode("", None, hfid_stored=False) for node_id in ids},
        whole={node_id: FakeNode("W", [node_id]) for node_id in ids},
    )

    hfids = await _reader(loader).load_hfids(ids)

    assert hfids == {"n1": ["n1"], "n2": ["n2"], "n3": ["n3"]}
    assert loader.calls == [
        (["n1", "n2"], HFID_FIELDS),
        (["n3"], HFID_FIELDS),
        (["n1", "n2"], None),
        (["n3"], None),
    ]
