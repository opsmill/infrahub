from uuid import uuid4

from infrahub.task_manager.models import InfrahubEventFilter, RelatedNodesInfo


class TestInfrahubEventFilter:
    def test_add_event_type_filter_with_exclude_prefixes_only(self) -> None:
        """When only exclude_prefixes is provided, the filter should scope to the infrahub namespace prefix."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(exclude_prefixes=["infrahub.account."])

        assert event_filter.event is not None
        assert event_filter.event.prefix == ["infrahub."]
        assert event_filter.event.exclude_prefix == ["infrahub.account."]

    def test_add_event_type_filter_with_event_type_only(self) -> None:
        """When event_type is provided, it takes priority and no prefix is set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter(event_type=["infrahub.branch.created"])

        assert event_filter.event is not None
        assert event_filter.event.name == ["infrahub.branch.created"]
        assert not event_filter.event.prefix

    def test_add_event_type_filter_with_no_args(self) -> None:
        """When no arguments are provided, the event filter is not set."""
        event_filter = InfrahubEventFilter()
        event_filter.add_event_type_filter()

        assert event_filter.event is None


class TestRelatedNodesInfo:
    def test_related_nodes_without_a_kind_are_omitted(self) -> None:
        """A node whose vertex is gone from the graph has no kind and cannot be described."""
        flow_id = uuid4()
        related_nodes = RelatedNodesInfo()
        related_nodes.add_nodes(flow_id=flow_id, node_ids=["resolvable", "missing"])
        related_nodes.nodes["resolvable"].kind = "BuiltinTag"

        assert [node.id for node in related_nodes.get_related_nodes(flow_id=flow_id)] == ["resolvable"]
        assert related_nodes.get_related_nodes_as_dict(flow_id=flow_id) == [{"id": "resolvable", "kind": "BuiltinTag"}]

    def test_first_related_node_skips_those_without_a_kind(self) -> None:
        """The deprecated single-node fields stay consistent with the related nodes list."""
        flow_id = uuid4()
        related_nodes = RelatedNodesInfo()
        related_nodes.add_nodes(flow_id=flow_id, node_ids=["missing", "resolvable"])
        related_nodes.nodes["resolvable"].kind = "BuiltinTag"

        first = related_nodes.get_first_related_node(flow_id=flow_id)

        assert first is not None
        assert first.id == "resolvable"

    def test_no_related_node_has_a_kind(self) -> None:
        flow_id = uuid4()
        related_nodes = RelatedNodesInfo()
        related_nodes.add_nodes(flow_id=flow_id, node_ids=["missing"])

        assert related_nodes.get_related_nodes(flow_id=flow_id) == []
        assert related_nodes.get_first_related_node(flow_id=flow_id) is None

    def test_unknown_flow_has_no_related_nodes(self) -> None:
        assert RelatedNodesInfo().get_related_nodes(flow_id=uuid4()) == []
