from uuid import uuid4

from infrahub.task_manager.flow_run.models import RelatedNodesInfo


class TestRelatedNodesInfo:
    def test_add_node_registers_in_nodes_and_flow(self) -> None:
        info = RelatedNodesInfo()
        flow_id = uuid4()

        info.add_node(flow_id=flow_id, node_id="node-1")

        assert info.get_related_nodes(flow_id=flow_id) == [info.nodes["node-1"]]
        assert info.nodes["node-1"].id == "node-1"

    def test_add_nodes_registers_all(self) -> None:
        info = RelatedNodesInfo()
        flow_id = uuid4()

        info.add_nodes(flow_id=flow_id, node_ids=["node-1", "node-2"])

        assert [node.id for node in info.get_related_nodes(flow_id=flow_id)] == ["node-1", "node-2"]

    def test_same_node_id_is_shared_across_flows(self) -> None:
        info = RelatedNodesInfo()
        flow_a = uuid4()
        flow_b = uuid4()

        info.add_node(flow_id=flow_a, node_id="shared")
        info.add_node(flow_id=flow_b, node_id="shared")

        assert info.get_unique_related_node_ids() == ["shared"]
        assert info.get_related_nodes(flow_id=flow_a)[0] is info.get_related_nodes(flow_id=flow_b)[0]

    def test_adding_same_node_twice_keeps_single_entry(self) -> None:
        info = RelatedNodesInfo()
        flow_id = uuid4()

        info.add_node(flow_id=flow_id, node_id="node-1")
        info.add_node(flow_id=flow_id, node_id="node-1")

        assert info.get_unique_related_node_ids() == ["node-1"]
        assert len(info.get_related_nodes(flow_id=flow_id)) == 1

    def test_get_related_nodes_empty_for_unknown_flow(self) -> None:
        info = RelatedNodesInfo()

        assert info.get_related_nodes(flow_id=uuid4()) == []

    def test_get_first_related_node(self) -> None:
        info = RelatedNodesInfo()
        flow_id = uuid4()
        info.add_nodes(flow_id=flow_id, node_ids=["first", "second"])

        first = info.get_first_related_node(flow_id=flow_id)

        assert first is not None
        assert first.id == "first"

    def test_get_first_related_node_none_when_absent(self) -> None:
        info = RelatedNodesInfo()

        assert info.get_first_related_node(flow_id=uuid4()) is None

    def test_get_related_nodes_as_dict(self) -> None:
        info = RelatedNodesInfo()
        flow_id = uuid4()
        info.add_node(flow_id=flow_id, node_id="node-1")
        info.nodes["node-1"].kind = "TestThing"

        assert info.get_related_nodes_as_dict(flow_id=flow_id) == [{"id": "node-1", "kind": "TestThing"}]

    def test_get_related_nodes_as_dict_empty_for_unknown_flow(self) -> None:
        info = RelatedNodesInfo()

        assert info.get_related_nodes_as_dict(flow_id=uuid4()) == []
