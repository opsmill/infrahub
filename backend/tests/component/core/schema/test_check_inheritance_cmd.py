from dataclasses import dataclass

from infrahub.cli.db_commands.check_inheritance import check_inheritance
from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.generic_schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase


@dataclass
class DatabaseNodeWithLabels:
    n_uuid: str
    n_labels: set[str]
    branch: str
    status: str

    def __hash__(self) -> int:
        return hash((self.n_uuid, frozenset(self.n_labels)))


class TestCheckInheritance:
    async def get_database_nodes_with_labels(self, db: InfrahubDatabase) -> set[DatabaseNodeWithLabels]:
        query = """
MATCH (n:TestPerson)-[e:IS_PART_OF]->(:Root)
WITH DISTINCT n, e.branch AS branch
CALL (n, branch) {
    MATCH (n)-[e:IS_PART_OF {branch: branch}]->(:Root)
    ORDER BY e.from DESC
    RETURN e
    LIMIT 1
}
RETURN n.uuid AS n_uuid, labels(n) AS n_labels, e.branch AS branch, e.status AS status
        """
        results = await db.execute_query(query=query)
        return {
            DatabaseNodeWithLabels(
                n_uuid=result.get("n_uuid"),
                n_labels=set(result.get("n_labels")),
                branch=result.get("branch"),
                status=result.get("status"),
            )
            for result in results
        }

    async def test_identify_and_fix_inheritance_issues(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        person_john_main: Node,
        register_internal_models_schema: SchemaBranch,
    ) -> None:
        main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(db=db, branch=default_branch, schema=main_schema_branch)
        main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=main_schema_branch)

        # verify no inheritance problems to start with
        result = await check_inheritance(db=db, fix=False)
        assert result is True

        # add a generic to the schema
        main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=main_schema_branch)
        schema_generic = GenericSchema(
            name="FoodPerson",
            namespace="Test",
            attributes=[AttributeSchema(name="favorite_food", kind="Text", optional=True)],
        )
        registry.schema.set(name="TestFoodPerson", branch=default_branch.name, schema=schema_generic)
        person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)
        person_schema.inherit_from = ["TestFoodPerson"]
        registry.schema.set(name=person_schema.kind, branch=default_branch.name, schema=person_schema)
        registry.schema.process_schema_branch(name=default_branch.name)
        updated_main_schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        await registry.schema.load_schema_to_db(db=db, branch=default_branch, schema=updated_main_schema_branch)

        # verify inheritance problems exist
        result = await check_inheritance(db=db, fix=False)
        assert result is False

        # fix the inheritance problems
        result = await check_inheritance(db=db, fix=True)
        assert result is True

        # verify inheritance is updated
        db_nodes_with_labels = await self.get_database_nodes_with_labels(db=db)
        assert db_nodes_with_labels == {
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "CoreNode", "Node"},
                branch=default_branch.name,
                status="deleted",
            ),
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "TestFoodPerson", "CoreNode", "Node"},
                branch=default_branch.name,
                status="active",
            ),
        }

        # un-update the inheritance on a branch
        main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=main_schema_branch)
        branch = await create_branch(db=db, branch_name="mulligan-branch")
        registry.schema.set_schema_branch(name=branch.name, schema=main_schema_branch)
        person_schema = registry.schema.get_node_schema(name="TestPerson", branch=branch)
        person_schema.inherit_from = []
        registry.schema.set(name=person_schema.kind, branch=branch.name, schema=person_schema)
        registry.schema.process_schema_branch(name=branch.name)
        updated_main_schema_branch = registry.schema.get_schema_branch(name=branch.name)
        await registry.schema.load_schema_to_db(db=db, branch=branch, schema=updated_main_schema_branch)

        # verify inheritance problems exist
        result = await check_inheritance(db=db, fix=False)
        assert result is False

        # fix the inheritance problems
        result = await check_inheritance(db=db, fix=True)
        assert result is True

        # verify inheritance is updated
        db_nodes_with_labels = await self.get_database_nodes_with_labels(db=db)
        assert db_nodes_with_labels == {
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "CoreNode", "Node"},
                branch=default_branch.name,
                status="deleted",
            ),
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "TestFoodPerson", "CoreNode", "Node"},
                branch=default_branch.name,
                status="active",
            ),
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "TestFoodPerson", "CoreNode", "Node"},
                branch=branch.name,
                status="deleted",
            ),
            DatabaseNodeWithLabels(
                n_uuid=person_john_main.id,
                n_labels={"TestPerson", "CoreNode", "Node"},
                branch=branch.name,
                status="active",
            ),
        }

        main_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
        registry.schema.set_schema_branch(name=default_branch.name, schema=main_schema_branch)
        main_person = await NodeManager.get_one(db=db, branch=default_branch, id=person_john_main.id)
        assert main_person.favorite_food.value is None

        branch_schema_branch = await registry.schema.load_schema_from_db(db=db, branch=branch)
        registry.schema.set_schema_branch(name=branch.name, schema=branch_schema_branch)
        branch_person = await NodeManager.get_one(db=db, branch=branch, id=person_john_main.id)
        assert not hasattr(branch_person, "favorite_food")
