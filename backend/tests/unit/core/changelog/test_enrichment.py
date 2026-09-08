from __future__ import annotations

from infrahub.core.changelog.enrichment import NodeLabelLoader, NodeLabels


class RecordingReader:
    """Test double for NodeLabelReader: returns preset labels and records the IDs it was asked for."""

    def __init__(self, labels: dict[str, NodeLabels]) -> None:
        self._labels = labels
        self.calls: list[list[str]] = []

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        self.calls.append(node_ids)
        return {node_id: self._labels[node_id] for node_id in node_ids if node_id in self._labels}

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        return {node_id: labels.hfid for node_id, labels in (await self.load_labels(node_ids)).items()}


class FailingReader:
    """Test double for NodeLabelReader that always raises, standing in for a read failure."""

    async def load_labels(self, node_ids: list[str]) -> dict[str, NodeLabels]:
        raise RuntimeError("label backend unavailable")

    async def load_hfids(self, node_ids: list[str]) -> dict[str, list[str] | None]:
        raise RuntimeError("label backend unavailable")


async def test_load_labels_deduplicates_sorts_and_drops_empty_ids() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"]), "b": NodeLabels("B", ["b"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["b", "", "a", "a", "b"])

    assert reader.calls == [["a", "b"]]
    assert result == {"a": NodeLabels("A", ["a"]), "b": NodeLabels("B", ["b"])}


async def test_load_labels_on_empty_input_never_reads() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["", ""])

    assert result == {}
    assert reader.calls == []


async def test_load_labels_holds_only_the_nodes_the_reader_found() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a"])})

    result = await NodeLabelLoader(reader=reader).load_labels(["a", "missing"])

    assert result == {"a": NodeLabels("A", ["a"])}


async def test_load_hfids_projects_only_the_hfid() -> None:
    reader = RecordingReader({"a": NodeLabels("A", ["a", "x"]), "b": NodeLabels("B", None)})

    result = await NodeLabelLoader(reader=reader).load_hfids(["a", "b"])

    assert result == {"a": ["a", "x"], "b": None}


async def test_load_labels_degrades_to_empty_when_the_reader_fails() -> None:
    result = await NodeLabelLoader(reader=FailingReader()).load_labels(["a", "b"])

    assert result == {}


async def test_load_hfids_degrades_to_empty_when_the_reader_fails() -> None:
    result = await NodeLabelLoader(reader=FailingReader()).load_hfids(["a", "b"])

    assert result == {}
