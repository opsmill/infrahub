from infrahub.core import registry
from infrahub.core.branch.models import Branch
from infrahub.core.constants import BranchSupportType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.graph.m040_duplicated_attributes import Migration040
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.db_validation import validate_no_duplicate_attributes


class TestMigration040:
    async def _prepare_branch(self, db: InfrahubDatabase, branch: Branch):
        previous_schema_branch = registry.schema.get_schema_branch(name=branch.name)
        previous_car_schema = previous_schema_branch.get_node(name="TestCar", duplicate=False)
        new_car_schema = previous_car_schema.duplicate()
        new_car_schema.attributes.append(AttributeSchema(name="smell", kind="Text", branch=BranchSupportType.AWARE))
        new_schema_branch = previous_schema_branch.duplicate()
        new_schema_branch.set(name="TestCar", schema=new_car_schema)

        # add the "smell" attribute once through the normal migration
        migration_errors = await schema_apply_migrations(
            message=SchemaApplyMigrationData(
                branch=branch,
                previous_schema=previous_schema_branch,
                new_schema=new_schema_branch,
                migrations=[
                    SchemaUpdateMigrationInfo(
                        path=SchemaPath(schema_kind="TestCar", path_type=SchemaPathType.ATTRIBUTE, field_name="smell"),
                        migration_name="node.attribute.add",
                    )
                ],
                at=Timestamp(),
            )
        )
        assert not migration_errors

        # Fabricate the error state a concurrent migration race used to produce: for every node that just
        # gained the attribute, copy the HAS_ATTRIBUTE path and the attribute's HAS_VALUE/IS_PROTECTED paths
        # onto a second Attribute vertex (fresh uuid) pointing at the same value vertices. Deterministic,
        # unlike racing the migration against itself, which does not reliably duplicate under CI load.
        await self._duplicate_attribute(db=db, branch=branch, attr_name="smell")

        # validate the error state
        errors = await validate_no_duplicate_attributes(db=db, branch=branch)
        assert errors

        registry.schema.set(name="TestCar", branch=branch.name, schema=new_car_schema)

    async def _duplicate_attribute(self, db: InfrahubDatabase, branch: Branch, attr_name: str) -> None:
        query = """
        MATCH (n:Node)-[hae:HAS_ATTRIBUTE {branch: $branch_name, status: "active"}]->(a:Attribute {name: $attr_name})
        WHERE hae.to IS NULL
        CALL (n, hae, a) {
            CREATE (dup:Attribute)
            SET dup = properties(a)
            CREATE (n)-[new_hae:HAS_ATTRIBUTE]->(dup)
            SET new_hae = properties(hae)
            SET dup.uuid = randomUUID()
            RETURN dup
        }
        WITH dup, a
        MATCH (a)-[e {branch: $branch_name, status: "active"}]->(peer)
        WHERE e.to IS NULL
        CALL (dup, e, peer) {
            CREATE (dup)-[new_e:$(type(e))]->(peer)
            SET new_e = properties(e)
        }
        """
        await db.execute_query(query=query, params={"branch_name": branch.name, "attr_name": attr_name})

    async def test_clean_duplicated_attributes(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        car_accord_main: Node,
        car_camry_main: Node,
    ) -> None:
        branch = await create_branch(db=db, branch_name="dup-attrs")

        # set the error state on main
        await self._prepare_branch(db=db, branch=default_branch)
        # set the error state on a branch
        await self._prepare_branch(db=db, branch=branch)

        # set values on main
        accord_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        accord_main.smell.value = "good"
        await accord_main.save(db=db)
        camry_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
        camry_main.smell.value = "okay"
        await camry_main.save(db=db)

        # set values on a branch
        accord_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
        accord_branch.smell.value = "bad"
        await accord_branch.save(db=db)
        camry_branch = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
        camry_branch.smell.value = "terrible"
        await camry_branch.save(db=db)

        migration = Migration040.init(db=db)
        result = await migration.execute(migration_input=MigrationInput(db=db))
        assert not result.errors

        # validate the result
        errors = await validate_no_duplicate_attributes(db=db, branch=default_branch)
        assert not errors
        errors = await validate_no_duplicate_attributes(db=db, branch=branch)
        assert not errors

        # validate values on main
        accord_main = await NodeManager.get_one(db=db, id=car_accord_main.id)
        assert accord_main.smell.value == "good"
        camry_main = await NodeManager.get_one(db=db, id=car_camry_main.id)
        assert camry_main.smell.value == "okay"

        # validate values on a branch
        accord_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch)
        assert accord_branch.smell.value == "bad"
        camry_branch = await NodeManager.get_one(db=db, id=car_camry_main.id, branch=branch)
        assert camry_branch.smell.value == "terrible"
