from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.node_diff_index import NodeDiffIndex
from infrahub.core.validators.uniqueness.scope import UniquenessConstraintScoper


class _RecordingResolver:
    """Test double returning a fixed dependent set and capturing what it was asked to resolve."""

    def __init__(self, dependents: set[str]) -> None:
        self.dependents = dependents
        self.calls: list[tuple[str, str, list[str]]] = []

    async def resolve(self, node_kind: str, relationship_identifier: str, peer_uuids: list[str]) -> set[str]:
        self.calls.append((node_kind, relationship_identifier, peer_uuids))
        return set(self.dependents)


def _scoper(schema_branch: SchemaBranch, resolver: _RecordingResolver, node_diffs: list[NodeDiffFieldSummary]):
    node_diff_index = NodeDiffIndex()
    node_diff_index.initialize(node_diffs)
    return UniquenessConstraintScoper(
        schema_branch=schema_branch, dependent_resolver=resolver, node_diff_index=node_diff_index
    )


class TestUniquenessConstraintScoper:
    async def test_same_kind_change_scopes_to_changed_nodes(
        self, car_person_schema: SchemaBranch, default_branch: Branch
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        scoper = _scoper(
            schema_branch,
            _RecordingResolver(dependents=set()),
            [NodeDiffFieldSummary(kind="TestPerson", attribute_names={"name"}, node_uuids={"person-1", "person-2"})],
        )
        person_schema = schema_branch.get(name="TestPerson")

        assert scoper.requires_validation(schema=person_schema) is True
        assert await scoper.affected_node_uuids(schema=person_schema) == ["person-1", "person-2"]

    async def test_triggered_without_node_uuids_falls_back_to_full_scan(
        self, car_person_schema: SchemaBranch, default_branch: Branch
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        scoper = _scoper(
            schema_branch,
            _RecordingResolver(dependents=set()),
            [NodeDiffFieldSummary(kind="TestPerson", attribute_names={"name"})],
        )
        person_schema = schema_branch.get(name="TestPerson")

        assert scoper.requires_validation(schema=person_schema) is True
        assert await scoper.affected_node_uuids(schema=person_schema) is None

    async def test_unrelated_field_change_does_not_trigger(
        self, car_person_schema: SchemaBranch, default_branch: Branch
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        # height is not part of any TestPerson uniqueness constraint
        scoper = _scoper(
            schema_branch,
            _RecordingResolver(dependents=set()),
            [NodeDiffFieldSummary(kind="TestPerson", attribute_names={"height"}, node_uuids={"person-1"})],
        )
        person_schema = schema_branch.get(name="TestPerson")

        assert scoper.requires_validation(schema=person_schema) is False
        assert await scoper.affected_node_uuids(schema=person_schema) is None

    async def test_cross_kind_peer_change_resolves_dependents(
        self, car_person_schema: SchemaBranch, default_branch: Branch
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        car_schema = schema_branch.get_node(name="TestCar")
        car_schema.uniqueness_constraints = [["owner__name"]]
        registry.schema.register_schema(schema=SchemaRoot(nodes=[car_schema]), branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        resolver = _RecordingResolver(dependents={"car-1", "car-2"})
        # a change to the peer kind's name, with no change to TestCar itself
        scoper = _scoper(
            schema_branch,
            resolver,
            [NodeDiffFieldSummary(kind="TestPerson", attribute_names={"name"}, node_uuids={"person-1"})],
        )
        car_schema = schema_branch.get(name="TestCar")

        assert scoper.requires_validation(schema=car_schema) is True
        assert await scoper.affected_node_uuids(schema=car_schema) == ["car-1", "car-2"]
        # the peer change is routed to the resolver as a single call carrying the changed peer uuids
        owner_identifier = car_schema.get_relationship(name="owner").get_identifier()
        assert resolver.calls == [("TestCar", owner_identifier, ["person-1"])]

    async def test_cross_kind_without_known_peer_uuids_falls_back_to_full_scan(
        self, car_person_schema: SchemaBranch, default_branch: Branch
    ) -> None:
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        car_schema = schema_branch.get_node(name="TestCar")
        car_schema.uniqueness_constraints = [["owner__name"]]
        registry.schema.register_schema(schema=SchemaRoot(nodes=[car_schema]), branch=default_branch.name)
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)

        resolver = _RecordingResolver(dependents={"car-1"})
        # the peer changed but its node uuids are unknown, so the dependents cannot be resolved
        scoper = _scoper(
            schema_branch,
            resolver,
            [NodeDiffFieldSummary(kind="TestPerson", attribute_names={"name"})],
        )
        car_schema = schema_branch.get(name="TestCar")

        assert scoper.requires_validation(schema=car_schema) is True
        assert await scoper.affected_node_uuids(schema=car_schema) is None
        assert not resolver.calls  # resolver is never called when the peer uuids are unknown
