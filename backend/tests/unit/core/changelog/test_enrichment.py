from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from infrahub.core.branch import Branch
from infrahub.core.changelog.enrichment import (
    HFID_FIELDS,
    LABEL_FIELDS,
    DbNodeLabelReader,
    LabelsFromStorage,
    NodeLabelLoader,
    NodeLabels,
)
from infrahub.core.constants.schema import DISPLAY_LABEL_ATTRIBUTE_NAME, HFID_ATTRIBUTE_NAME
from infrahub.core.query.node import NodeStoredLabels
from infrahub.core.schema import AttributeSchema, NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


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


@dataclass
class RecordingStoredLabelLoader:
    """Test double for the stored-label loader: serves preset stored labels and records each call."""

    stored: dict[str, NodeStoredLabels] = field(default_factory=dict)
    calls: list[tuple[list[str], list[str]]] = field(default_factory=list)

    async def __call__(
        self, *, db: InfrahubDatabase, ids: list[str], branch: Branch, label_names: list[str]
    ) -> dict[str, NodeStoredLabels]:
        self.calls.append((ids, label_names))
        return {node_id: self.stored[node_id] for node_id in ids if node_id in self.stored}


WITH_HFID = "TestWithHfid"
WITHOUT_HFID = "TestWithoutHfid"
SCHEMA_NODE = "SchemaThing"


def _schema_branch() -> SchemaBranch:
    schema_branch = SchemaBranch(cache={}, name="main")
    for namespace, name, hfid in (
        ("Test", "WithHfid", ["name__value"]),
        ("Test", "WithoutHfid", None),
        ("Schema", "Thing", ["name__value"]),
    ):
        schema = NodeSchema(
            name=name,
            namespace=namespace,
            display_label="name__value",
            human_friendly_id=hfid,
            attributes=[AttributeSchema(name="name", kind="Text")],
        )
        schema_branch.set(name=schema.kind, schema=schema)
    return schema_branch


def _from_storage(kind: str, display_label: str | None, hfid: list[str] | None) -> LabelsFromStorage:
    return LabelsFromStorage(
        stored=NodeStoredLabels(kind=kind, display_label=display_label, hfid=hfid),
        schema=_schema_branch().get(name=kind, duplicate=False),
    )


@dataclass
class FromStorageCase:
    name: str
    kind: str
    display_label: str | None
    hfid: list[str] | None
    knows_hfid: bool
    knows_labels: bool
    expected_hfid: list[str] | None = None


FROM_STORAGE_CASES = [
    FromStorageCase(
        name="both_labels_stored",
        kind=WITH_HFID,
        display_label="A",
        hfid=["a"],
        knows_hfid=True,
        knows_labels=True,
        expected_hfid=["a"],
    ),
    FromStorageCase(
        name="hfid_defined_without_stored_hfid",
        kind=WITH_HFID,
        display_label="A",
        hfid=None,
        knows_hfid=False,
        knows_labels=False,
    ),
    FromStorageCase(
        name="display_label_not_stored",
        kind=WITH_HFID,
        display_label=None,
        hfid=["a"],
        knows_hfid=True,
        knows_labels=False,
        expected_hfid=["a"],
    ),
    FromStorageCase(
        name="kind_without_hfid",
        kind=WITHOUT_HFID,
        display_label="B",
        hfid=None,
        knows_hfid=True,
        knows_labels=True,
        expected_hfid=None,
    ),
    FromStorageCase(
        name="kind_without_hfid_ignores_a_leftover_stored_hfid",
        kind=WITHOUT_HFID,
        display_label="B",
        hfid=["leftover"],
        knows_hfid=True,
        knows_labels=True,
        expected_hfid=None,
    ),
]


@pytest.mark.parametrize("case", FROM_STORAGE_CASES, ids=lambda case: case.name)
def test_labels_from_storage_tell_which_labels_storage_gives(case: FromStorageCase) -> None:
    from_storage = _from_storage(kind=case.kind, display_label=case.display_label, hfid=case.hfid)

    assert from_storage.knows_hfid() is case.knows_hfid
    assert from_storage.knows_labels() is case.knows_labels
    if case.knows_hfid:
        assert from_storage.hfid == case.expected_hfid


def test_labels_from_storage_refuse_an_hfid_storage_does_not_give() -> None:
    from_storage = _from_storage(kind=WITH_HFID, display_label="A", hfid=None)

    with pytest.raises(ValueError, match=r"^the stored labels of this TestWithHfid do not give its HFID$"):
        _ = from_storage.hfid


def test_labels_from_storage_refuse_a_display_label_storage_does_not_give() -> None:
    from_storage = _from_storage(kind=WITH_HFID, display_label=None, hfid=["a"])

    with pytest.raises(ValueError, match=r"^the stored labels of this TestWithHfid do not give its display label$"):
        _ = from_storage.display_label


def _reader(
    loader: RecordingNodeLoader, stored_loader: RecordingStoredLabelLoader | None = None, page_size: int = 100
) -> DbNodeLabelReader:
    return DbNodeLabelReader(
        db=UnusableDatabase(),
        branch=Branch(name="main"),
        schema_branch=_schema_branch(),
        stored_label_loader=stored_loader or RecordingStoredLabelLoader(),
        node_loader=loader,
        page_size=page_size,
    )


async def test_reader_takes_the_labels_storage_settles_without_loading_the_nodes() -> None:
    stored_loader = RecordingStoredLabelLoader(
        stored={
            "with_hfid": NodeStoredLabels(kind=WITH_HFID, display_label="A", hfid=["a"]),
            "without_hfid": NodeStoredLabels(kind=WITHOUT_HFID, display_label="B", hfid=None),
        }
    )
    loader = RecordingNodeLoader(restricted={}, whole={})

    labels = await _reader(loader, stored_loader).load_labels(["with_hfid", "without_hfid"])

    assert labels == {
        "with_hfid": NodeLabels(display_label="A", hfid=["a"]),
        "without_hfid": NodeLabels(display_label="B", hfid=None),
    }
    assert stored_loader.calls == [(["with_hfid", "without_hfid"], [DISPLAY_LABEL_ATTRIBUTE_NAME, HFID_ATTRIBUTE_NAME])]
    assert loader.calls == []


async def test_reader_loads_the_nodes_storage_does_not_settle() -> None:
    stored_loader = RecordingStoredLabelLoader(
        stored={
            "settled": NodeStoredLabels(kind=WITH_HFID, display_label="A", hfid=["a"]),
            "no_label": NodeStoredLabels(kind=WITH_HFID, display_label=None, hfid=["b"]),
            "no_hfid": NodeStoredLabels(kind=WITH_HFID, display_label="C", hfid=None),
            "schema_node": NodeStoredLabels(kind=SCHEMA_NODE, display_label="D", hfid=["d"]),
            "dropped_kind": NodeStoredLabels(kind="TestDropped", display_label="E", hfid=["e"]),
        }
    )
    loaded = {node_id: FakeNode(f"Loaded {node_id}", [node_id]) for node_id in stored_loader.stored}
    loader = RecordingNodeLoader(restricted=loaded, whole={})

    labels = await _reader(loader, stored_loader).load_labels(list(stored_loader.stored))

    assert labels == {
        "settled": NodeLabels(display_label="A", hfid=["a"]),
        **{
            node_id: NodeLabels(display_label=f"Loaded {node_id}", hfid=[node_id])
            for node_id in ("no_label", "no_hfid", "schema_node", "dropped_kind")
        },
    }
    assert loader.calls == [(["no_label", "no_hfid", "schema_node", "dropped_kind"], LABEL_FIELDS)]


async def test_reader_takes_the_hfids_storage_settles_whatever_the_display_label() -> None:
    stored_loader = RecordingStoredLabelLoader(
        stored={
            "no_label": NodeStoredLabels(kind=WITH_HFID, display_label=None, hfid=["a"]),
            "without_hfid": NodeStoredLabels(kind=WITHOUT_HFID, display_label=None, hfid=None),
            "no_hfid": NodeStoredLabels(kind=WITH_HFID, display_label=None, hfid=None),
        }
    )
    loader = RecordingNodeLoader(restricted={"no_hfid": FakeNode("", ["computed"])}, whole={})

    hfids = await _reader(loader, stored_loader).load_hfids(["no_label", "without_hfid", "no_hfid"])

    assert hfids == {"no_label": ["a"], "without_hfid": None, "no_hfid": ["computed"]}
    assert stored_loader.calls == [(["no_label", "without_hfid", "no_hfid"], [HFID_ATTRIBUTE_NAME])]
    assert loader.calls == [(["no_hfid"], HFID_FIELDS)]


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


async def test_reader_pages_both_the_restricted_read_and_the_reload() -> None:
    ids = ["n1", "n2", "n3"]
    loader = RecordingNodeLoader(
        restricted={node_id: FakeNode("", None, hfid_stored=False) for node_id in ids},
        whole={node_id: FakeNode("W", [node_id]) for node_id in ids},
    )

    hfids = await _reader(loader, page_size=2).load_hfids(ids)

    assert hfids == {"n1": ["n1"], "n2": ["n2"], "n3": ["n3"]}
    assert loader.calls == [
        (["n1", "n2"], HFID_FIELDS),
        (["n3"], HFID_FIELDS),
        (["n1", "n2"], None),
        (["n3"], None),
    ]
