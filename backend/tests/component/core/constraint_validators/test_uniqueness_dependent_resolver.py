import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import RelationshipCardinality, RelationshipDirection
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import AttributeSchema, NodeSchema, SchemaRoot
from infrahub.core.schema.relationship_schema import RelationshipSchema
from infrahub.core.validators.uniqueness.dependent_resolver import UniquenessDependentResolver
from infrahub.database import InfrahubDatabase

TREE_NODE_KIND = "TestingTreeNode"
TREE_RELATIONSHIP_IDENTIFIER = "testingtreenode__testingtreenode"

# a kind whose relationship points at its own kind: `parent` and `children` share one identifier and
# are told apart only by the direction of the edges around the Relationship vertex
TREE_NODE = NodeSchema(
    name="TreeNode",
    namespace="Testing",
    generate_profile=False,
    attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
    relationships=[
        RelationshipSchema(
            name="parent",
            peer=TREE_NODE_KIND,
            identifier=TREE_RELATIONSHIP_IDENTIFIER,
            cardinality=RelationshipCardinality.ONE,
            direction=RelationshipDirection.OUTBOUND,
            optional=True,
        ),
        RelationshipSchema(
            name="children",
            peer=TREE_NODE_KIND,
            identifier=TREE_RELATIONSHIP_IDENTIFIER,
            cardinality=RelationshipCardinality.MANY,
            direction=RelationshipDirection.INBOUND,
            optional=True,
        ),
    ],
)


def _owner_relationship(default_branch: Branch) -> RelationshipSchema:
    car_schema = registry.schema.get("TestCar", branch=default_branch)
    return car_schema.get_relationship("owner")


class TestUniquenessDependentResolver:
    async def test_resolves_nodes_referencing_changed_peers(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_volt_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        person_john_main: Node,
        default_branch: Branch,
    ) -> None:
        resolver = UniquenessDependentResolver(db=db, branch=default_branch)

        dependents = await resolver.resolve(
            node_kind="TestCar",
            relationship_identifier=_owner_relationship(default_branch).get_identifier(),
            relationship_direction=_owner_relationship(default_branch).direction,
            peer_uuids=[person_john_main.id],
        )

        # the cars owned by john, and not those owned by anyone else
        assert dependents == {car_accord_main.id, car_volt_main.id, car_prius_main.id}
        assert car_camry_main.id not in dependents

    async def test_empty_peer_uuids_returns_empty(
        self, db: InfrahubDatabase, car_accord_main: Node, default_branch: Branch
    ) -> None:
        resolver = UniquenessDependentResolver(db=db, branch=default_branch)

        dependents = await resolver.resolve(
            node_kind="TestCar",
            relationship_identifier=_owner_relationship(default_branch).get_identifier(),
            relationship_direction=_owner_relationship(default_branch).direction,
            peer_uuids=[],
        )

        assert dependents == set()

    async def test_covers_default_branch_changes_made_after_the_branch_forked(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        person_john_main: Node,
        default_branch: Branch,
    ) -> None:
        # fork a branch, THEN add a car on the default branch after the fork
        feature_branch = await create_branch(branch_name="feature-branch", db=db)
        car_schema = registry.schema.get_node_schema("TestCar", branch=default_branch, duplicate=False)
        latecomer_car = await Node.init(db=db, schema=car_schema, branch=default_branch)
        await latecomer_car.new(db=db, name="latecomer", nbr_seats=2, is_electric=False, owner=person_john_main.id)
        await latecomer_car.save(db=db)

        resolver = UniquenessDependentResolver(db=db, branch=feature_branch)

        dependents = await resolver.resolve(
            node_kind="TestCar",
            relationship_identifier=_owner_relationship(default_branch).get_identifier(),
            relationship_direction=_owner_relationship(default_branch).direction,
            peer_uuids=[person_john_main.id],
        )

        # validation runs against the current default branch, so a relationship added to default after
        # the fork is included even though the branch's own view predates it
        assert latecomer_car.id in dependents
        assert car_accord_main.id in dependents

    async def test_post_fork_default_branch_deletion_excludes_when_branch_is_silent(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        person_john_main: Node,
        default_branch: Branch,
    ) -> None:
        # after the fork, accord is deleted on the DEFAULT branch; the input branch never touches
        # it, so the default branch's latest state decides and accord is excluded
        input_branch = await create_branch(branch_name="silent-branch", db=db)
        accord_on_main = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=default_branch)
        await accord_on_main.delete(db=db)

        resolver = UniquenessDependentResolver(db=db, branch=input_branch)

        dependents = await resolver.resolve(
            node_kind="TestCar",
            relationship_identifier=_owner_relationship(default_branch).get_identifier(),
            relationship_direction=_owner_relationship(default_branch).direction,
            peer_uuids=[person_john_main.id],
        )

        assert car_accord_main.id not in dependents
        assert car_prius_main.id in dependents

    async def test_excludes_node_whose_relationship_is_deleted_on_input_branch(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        person_john_main: Node,
        default_branch: Branch,
    ) -> None:
        # accord's owner relationship is active on the default branch; delete it only on the input branch
        input_branch = await create_branch(branch_name="delete-branch", db=db)
        accord_on_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=input_branch)
        await accord_on_branch.delete(db=db)

        resolver = UniquenessDependentResolver(db=db, branch=input_branch)

        dependents = await resolver.resolve(
            node_kind="TestCar",
            relationship_identifier=_owner_relationship(default_branch).get_identifier(),
            relationship_direction=_owner_relationship(default_branch).direction,
            peer_uuids=[person_john_main.id],
        )

        # the input-branch deletion overrides the default branch (it is what the merge will
        # produce), so accord is excluded; prius keeps its untouched relationship and stays
        assert car_accord_main.id not in dependents
        assert car_prius_main.id in dependents


class TestUniquenessDependentResolverSelfReferential:
    @pytest.fixture
    async def tree(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, Node]:
        registry.schema.register_schema(schema=SchemaRoot(nodes=[TREE_NODE]), branch=default_branch.name)

        root = await Node.init(db=db, schema=TREE_NODE_KIND, branch=default_branch)
        await root.new(db=db, name="root")
        await root.save(db=db)
        middle = await Node.init(db=db, schema=TREE_NODE_KIND, branch=default_branch)
        await middle.new(db=db, name="middle", parent=root.id)
        await middle.save(db=db)
        leaf = await Node.init(db=db, schema=TREE_NODE_KIND, branch=default_branch)
        await leaf.new(db=db, name="leaf", parent=middle.id)
        await leaf.save(db=db)

        return {"root": root, "middle": middle, "leaf": leaf}

    async def test_outbound_relationship_resolves_only_the_child_side(
        self, db: InfrahubDatabase, default_branch: Branch, tree: dict[str, Node]
    ) -> None:
        """A change to `middle` implicates the node whose `parent` is `middle`, not `middle`'s parent."""
        resolver = UniquenessDependentResolver(db=db, branch=default_branch)

        dependents = await resolver.resolve(
            node_kind=TREE_NODE_KIND,
            relationship_identifier=TREE_RELATIONSHIP_IDENTIFIER,
            relationship_direction=RelationshipDirection.OUTBOUND,
            peer_uuids=[tree["middle"].id],
        )

        assert dependents == {tree["leaf"].id}

    async def test_inbound_relationship_resolves_only_the_parent_side(
        self, db: InfrahubDatabase, default_branch: Branch, tree: dict[str, Node]
    ) -> None:
        """The same edges seen from `children` implicate the node holding `middle` as a child."""
        resolver = UniquenessDependentResolver(db=db, branch=default_branch)

        dependents = await resolver.resolve(
            node_kind=TREE_NODE_KIND,
            relationship_identifier=TREE_RELATIONSHIP_IDENTIFIER,
            relationship_direction=RelationshipDirection.INBOUND,
            peer_uuids=[tree["middle"].id],
        )

        assert dependents == {tree["root"].id}
