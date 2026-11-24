from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest

from infrahub.core import registry
from infrahub.core.constants import BranchSupportType, RelationshipStatus, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations import MIGRATION_MAP
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData, SchemaMigrationPathResponseData
from infrahub.core.migrations.schema.runner import SchemaMigrationRunner
from infrahub.core.migrations.schema.scheduler import MigrationScheduler
from infrahub.core.migrations.schema.tasks import MAX_CONCURRENT_MIGRATION_GROUPS, TaskSchemaPathMigrator
from infrahub.core.models import SchemaUpdateMigrationInfo
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema, RelationshipSchema, SchemaRoot
from infrahub.core.schema.attribute_schema import AttributeSchema
from infrahub.core.schema.definitions.core.template import core_object_template
from infrahub.core.schema_change.migration_recorder import NoRecordMigrationRecorder
from infrahub.core.timestamp import Timestamp
from infrahub.database.validation import verify_graph
from tests.adapters.migration_recorder import (
    MIGRATION_ENDED,
    MIGRATION_STARTED,
    REGISTER,
    MigrationRecorderCall,
    RecordingMigrationRecorder,
)
from tests.component.core.migrations.schema.second_run_helpers import register_candidate
from tests.conftest import do_car_person_schema_unregistered, do_empty_database, do_reset_registry

if TYPE_CHECKING:
    from collections.abc import Callable

    from infrahub.core.branch import Branch
    from infrahub.core.schema.schema_branch import SchemaBranch
    from infrahub.core.schema_change.migration_recorder import MigrationRecorder
    from infrahub.database import InfrahubDatabase


def _runner(db: InfrahubDatabase, recorder: MigrationRecorder) -> SchemaMigrationRunner:
    return SchemaMigrationRunner(
        scheduler=MigrationScheduler(migration_classes=MIGRATION_MAP),
        migrator=TaskSchemaPathMigrator(database=db),
        recorder=recorder,
        max_concurrent_groups=MAX_CONCURRENT_MIGRATION_GROUPS,
        log=logging.getLogger(__name__),
    )


async def _store_schema_ids(db: InfrahubDatabase, default_branch: Branch) -> None:
    """Store the registered schema, so that its elements get the IDs that let the diff see a rename."""
    schema = registry.schema.get_schema_branch(name=default_branch.name)
    await registry.schema.load_schema_to_db(schema=schema, branch=default_branch, db=db, at=Timestamp())


async def _load_car_change(
    db: InfrahubDatabase, branch: Branch, change_car: Callable[[NodeSchema], None], expected_migration_names: list[str]
) -> Timestamp:
    """Change the `TestCar` schema of the branch as a schema load does, and run the migrations the change gives."""

    def change_schema(candidate: SchemaBranch) -> None:
        car_schema = candidate.get_node(name="TestCar")
        change_car(car_schema)
        candidate.set(name="TestCar", schema=car_schema)

    return await _load_change(
        db=db, branch=branch, change_schema=change_schema, expected_migration_names=expected_migration_names
    )


async def _load_change(
    db: InfrahubDatabase,
    branch: Branch,
    change_schema: Callable[[SchemaBranch], None],
    expected_migration_names: list[str],
) -> Timestamp:
    """Change the schema of the branch as a schema load does, and run the migrations the change gives."""
    previous_schema = registry.schema.get_schema_branch(name=branch.name).duplicate()
    candidate = previous_schema.duplicate()
    change_schema(candidate)
    await register_candidate(db=db, branch=branch, candidate=candidate)
    validation = previous_schema.validate_update(other=candidate, diff=previous_schema.diff(other=candidate))
    assert sorted(migration.migration_name for migration in validation.migrations) == expected_migration_names

    at = Timestamp()
    errors = await _runner(db=db, recorder=NoRecordMigrationRecorder()).run(
        data=SchemaApplyMigrationData(
            branch=branch,
            previous_schema=previous_schema,
            new_schema=candidate,
            migrations=validation.migrations,
            at=at,
        )
    )

    assert errors == []
    return at


def _rename_color_and_add_a_new_color(car_schema: NodeSchema) -> None:
    car_schema.get_attribute(name="color").name = "paint"
    car_schema.attributes.append(AttributeSchema(name="color", kind="Text", optional=True, default_value="red"))


async def _car_ids(db: InfrahubDatabase, branch: Branch, filters: dict[str, object]) -> list[str]:
    """Return the cars whose stored attributes match; a loaded node would show the default of a missing attribute."""
    cars = await NodeManager.query(db=db, branch=branch, schema="TestCar", filters=filters)
    return [car.id for car in cars]


OPEN_ATTRIBUTE_EDGES_QUERY = """
MATCH (node:%(label)s)-[has_attribute:HAS_ATTRIBUTE]->(attribute:Attribute {name: $attribute_name})
WHERE has_attribute.branch = $branch_name AND has_attribute.to IS NULL
OPTIONAL MATCH (attribute)-[has_value:HAS_VALUE]->()
WHERE has_value.branch = $branch_name AND has_value.to IS NULL
RETURN node.uuid AS node_id, collect(DISTINCT has_attribute.status) AS attribute_statuses,
    collect(DISTINCT has_value.status) AS value_statuses
"""


async def _open_attribute_edge_statuses(
    db: InfrahubDatabase, node_label: str, attribute_name: str, branch_name: str
) -> dict[str, tuple[list[str], list[str]]]:
    """Return the statuses of the open edges of an attribute, by node; a load writes its closing and its new edges at one timestamp."""
    results = await db.execute_query(
        query=OPEN_ATTRIBUTE_EDGES_QUERY % {"label": node_label},
        params={"attribute_name": attribute_name, "branch_name": branch_name},
    )
    return {
        record["node_id"]: (sorted(record["attribute_statuses"]), sorted(record["value_statuses"]))
        for record in results
    }


ACTIVE_VALUE_LABELS_QUERY = """
MATCH (node:Node {uuid: $node_id})-[has_attribute:HAS_ATTRIBUTE]->(:Attribute {name: $attribute_name})-[has_value:HAS_VALUE]->(value)
WHERE all(edge IN [has_attribute, has_value] WHERE edge.branch = $branch_name AND edge.to IS NULL AND edge.status = "active")
RETURN labels(value) AS value_labels
"""


async def _active_value_labels(
    db: InfrahubDatabase, node_id: str, attribute_name: str, branch: Branch
) -> list[list[str]]:
    """Return the labels of the active value vertices of an attribute of a node."""
    results = await db.execute_query(
        query=ACTIVE_VALUE_LABELS_QUERY,
        params={"node_id": node_id, "attribute_name": attribute_name, "branch_name": branch.name},
    )
    return [sorted(record["value_labels"]) for record in results]


OPEN_RELATIONSHIP_EDGES_QUERY = """
MATCH (node:Node {uuid: $node_id})-[is_related:IS_RELATED]-(:Relationship {name: $identifier})
WHERE is_related.branch = $branch_name AND is_related.to IS NULL
RETURN is_related.status AS status
"""


async def _open_relationship_edge_statuses(
    db: InfrahubDatabase, node_id: str, identifier: str, branch: Branch
) -> list[str]:
    """Return the statuses of the open edges between a node and the relationships with an identifier."""
    results = await db.execute_query(
        query=OPEN_RELATIONSHIP_EDGES_QUERY,
        params={"node_id": node_id, "identifier": identifier, "branch_name": branch.name},
    )
    return sorted(record["status"] for record in results)


async def test_a_migration_reports_that_it_started_before_it_reports_its_result(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, car_accord_main: Node
) -> None:
    previous_schema = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = previous_schema.get_node(name="TestCar", duplicate=False).duplicate()
    new_car_schema.attributes.append(AttributeSchema(name="smell", kind="Text", branch=BranchSupportType.AWARE))
    new_schema = previous_schema.duplicate()
    new_schema.set(name="TestCar", schema=new_car_schema)
    migration = SchemaUpdateMigrationInfo(
        path=SchemaPath(schema_kind="TestCar", path_type=SchemaPathType.ATTRIBUTE, field_name="smell"),
        migration_name="node.attribute.add",
    )
    recorder = RecordingMigrationRecorder()

    errors = await _runner(db=db, recorder=recorder).run(
        data=SchemaApplyMigrationData(
            branch=default_branch,
            previous_schema=previous_schema,
            new_schema=new_schema,
            migrations=[migration],
            at=Timestamp(),
        )
    )

    assert errors == []
    assert recorder.calls == [
        MigrationRecorderCall(method=REGISTER, arguments={"migrations": [migration]}),
        MigrationRecorderCall(method=MIGRATION_STARTED, arguments={"position": 0}),
        MigrationRecorderCall(
            method=MIGRATION_ENDED,
            arguments={
                "position": 0,
                "result": SchemaMigrationPathResponseData(
                    migration_name="node.attribute.add",
                    schema_path=migration.path,
                    errors=[],
                    nbr_migrations_executed=1,
                ),
            },
        ),
    ]


async def test_an_attribute_renamed_while_a_new_attribute_takes_its_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
) -> None:
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "#444444"}) == [car_accord_main.id]
    await _store_schema_ids(db=db, default_branch=default_branch)

    await _load_car_change(
        db=db,
        branch=default_branch,
        change_car=_rename_color_and_add_a_new_color,
        expected_migration_names=["attribute.name.update", "node.attribute.add"],
    )

    assert await _car_ids(db=db, branch=default_branch, filters={"paint__value": "#444444"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "red"}) == [car_accord_main.id]
    await verify_graph(db=db, kinds=["TestCar"])


async def test_an_attribute_renamed_while_a_new_attribute_takes_its_name_on_a_branch(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    car_accord_main: Node,
) -> None:
    await _store_schema_ids(db=db, default_branch=default_branch)
    branch = await create_branch(db=db, branch_name="rename-and-reuse")

    await _load_car_change(
        db=db,
        branch=branch,
        change_car=_rename_color_and_add_a_new_color,
        expected_migration_names=["attribute.name.update", "node.attribute.add"],
    )

    assert await _car_ids(db=db, branch=branch, filters={"paint__value": "#444444"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=branch, filters={"color__value": "red"}) == [car_accord_main.id]
    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "#444444"}) == [car_accord_main.id]
    await verify_graph(db=db, kinds=["TestCar"])


async def test_an_attribute_removed_while_another_attribute_is_renamed_onto_its_name(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_schema_db: None,
    car_person_schema: SchemaBranch,
    person_john_main: Node,
) -> None:
    car = await Node.init(db=db, schema="TestCar", branch=default_branch)
    await car.new(db=db, name="civic", nbr_seats=4, is_electric=False, transmission="manual", owner=person_john_main.id)
    await car.save(db=db)
    await _store_schema_ids(db=db, default_branch=default_branch)

    def remove_color_and_rename_transmission(car_schema: NodeSchema) -> None:
        car_schema.attributes = [attribute for attribute in car_schema.attributes if attribute.name != "color"]
        car_schema.get_attribute(name="transmission").name = "color"

    await _load_car_change(
        db=db,
        branch=default_branch,
        change_car=remove_color_and_rename_transmission,
        expected_migration_names=["attribute.name.update", "node.attribute.remove"],
    )

    assert await _car_ids(db=db, branch=default_branch, filters={"color__value": "manual"}) == [car.id]
    await verify_graph(db=db, kinds=["TestCar"])


@dataclass(frozen=True)
class RenameData:
    car: str
    car_profile: str
    car_template: str
    truck: str
    truck_profile: str
    truck_template: str
    trailer: str
    person: str
    mechanic: str
    garage: str


def _rename_and_change_schema() -> SchemaRoot:
    schema = deepcopy(do_car_person_schema_unregistered())
    car = next(node for node in schema.nodes if node.name == "Car")
    car.attributes.extend(
        [
            AttributeSchema(name="nickname", kind="Text", optional=True),
            AttributeSchema(name="vin", kind="Text", optional=True),
            AttributeSchema(name="plate", kind="Text", optional=True),
            AttributeSchema(name="paint", kind="Text", optional=True, branch=BranchSupportType.AGNOSTIC),
            AttributeSchema(name="trim", kind="Text", optional=True),
        ]
    )
    car.uniqueness_constraints = [["name__value"], ["plate__value", "name__value"]]
    person = next(node for node in schema.nodes if node.name == "Person")
    person.relationships.append(
        RelationshipSchema(
            name="trailers", peer="TestTrailer", cardinality="many", identifier="testtrailer__towed_by", optional=True
        )
    )
    schema.nodes.extend(
        [
            NodeSchema(
                name="Truck",
                namespace="Test",
                attributes=[
                    AttributeSchema(name="name", kind="Text", unique=True),
                    AttributeSchema(name="cargo", kind="Text", optional=True),
                ],
            ),
            NodeSchema(
                name="Trailer",
                namespace="Test",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="towed_by",
                        peer="TestPerson",
                        cardinality="one",
                        optional=True,
                        identifier="testtrailer__towed_by",
                    )
                ],
            ),
            NodeSchema(
                name="Mechanic",
                namespace="Test",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="garages",
                        peer="TestGarage",
                        cardinality="many",
                        optional=True,
                        identifier="testgarage__mechanic",
                    )
                ],
            ),
            NodeSchema(
                name="Garage",
                namespace="Test",
                attributes=[AttributeSchema(name="name", kind="Text", unique=True)],
                relationships=[
                    RelationshipSchema(
                        name="mechanic",
                        peer="TestMechanic",
                        cardinality="one",
                        optional=True,
                        identifier="testgarage__mechanic",
                    )
                ],
            ),
        ]
    )
    for node in schema.nodes:
        node.generate_template = True
    return schema


@pytest.fixture(scope="class")
async def rename_schema(
    db: InfrahubDatabase, default_branch_scope_class: Branch, register_core_models_schema_scope_class: SchemaBranch
) -> SchemaBranch:
    await registry.schema.load_schema_to_db(
        schema=register_core_models_schema_scope_class, branch=default_branch_scope_class, db=db, at=Timestamp()
    )
    updated_schema = await registry.schema.load_schema_from_db(db=db, branch=default_branch_scope_class)
    registry.schema.set_schema_branch(name=default_branch_scope_class.name, schema=updated_schema)
    registry.schema.register_schema(
        schema=SchemaRoot(generics=[core_object_template]), branch=default_branch_scope_class.name
    )
    schema = registry.schema.register_schema(schema=_rename_and_change_schema(), branch=default_branch_scope_class.name)
    await _store_schema_ids(db=db, default_branch=default_branch_scope_class)
    return schema


async def _create_node(db: InfrahubDatabase, branch: Branch, schema: str, **values: object) -> str:
    node = await Node.init(db=db, schema=schema, branch=branch)
    await node.new(db=db, **values)
    await node.save(db=db)
    return node.id


@pytest.fixture(scope="class")
async def rename_data(
    db: InfrahubDatabase, default_branch_scope_class: Branch, rename_schema: SchemaBranch
) -> RenameData:
    branch = default_branch_scope_class
    john = await _create_node(db=db, branch=branch, schema="TestPerson", name="john")
    template_person = await _create_node(
        db=db, branch=branch, schema="TemplateTestPerson", template_name="person-template"
    )
    car_values = {
        "nickname": "speedy",
        "transmission": "manual",
        "vin": "vin-1",
        "paint": "red",
        "trim": "sport",
    }
    car = await _create_node(
        db=db, branch=branch, schema="TestCar", name="civic", plate="plate-1", owner=john, **car_values
    )
    car_profile = await _create_node(
        db=db, branch=branch, schema="ProfileTestCar", profile_name="car-profile", **car_values
    )
    car_template = await _create_node(
        db=db,
        branch=branch,
        schema="TemplateTestCar",
        template_name="car-template",
        plate="plate-1",
        owner=template_person,
        **car_values,
    )
    truck = await _create_node(db=db, branch=branch, schema="TestTruck", name="hauler", cargo="gravel")
    truck_profile = await _create_node(
        db=db, branch=branch, schema="ProfileTestTruck", profile_name="truck-profile", cargo="gravel"
    )
    truck_template = await _create_node(
        db=db, branch=branch, schema="TemplateTestTruck", template_name="truck-template", cargo="gravel"
    )
    trailer = await _create_node(db=db, branch=branch, schema="TestTrailer", name="trailer-1", towed_by=john)
    mechanic = await _create_node(db=db, branch=branch, schema="TestMechanic", name="mike")
    garage = await _create_node(db=db, branch=branch, schema="TestGarage", name="garage-1", mechanic=mechanic)
    return RenameData(
        car=car,
        car_profile=car_profile,
        car_template=car_template,
        truck=truck,
        truck_profile=truck_profile,
        truck_template=truck_template,
        trailer=trailer,
        person=john,
        mechanic=mechanic,
        garage=garage,
    )


class TestSchemaLoadsThatRenameAndChange:
    @pytest.fixture(scope="class", params=["default", "user"], ids=["default", "user"])
    def branch_kind(self, request: pytest.FixtureRequest) -> str:
        """The branch the loads run on; the empty database and the registry depend on it, so each kind starts from a fresh load."""
        return request.param

    @pytest.fixture(scope="class")
    async def empty_database_scope_class(self, db: InfrahubDatabase, branch_kind: str) -> None:
        await do_empty_database(db=db)

    @pytest.fixture(scope="class")
    async def reset_registry_scope_class(self, db: InfrahubDatabase, branch_kind: str) -> None:
        await do_reset_registry(db=db)

    @pytest.fixture(scope="class")
    async def target_branch(
        self, db: InfrahubDatabase, default_branch_scope_class: Branch, rename_data: RenameData, branch_kind: str
    ) -> Branch:
        if branch_kind == "default":
            return default_branch_scope_class
        return await create_branch(db=db, branch_name="rename-and-change")

    async def test_an_attribute_renamed_with_a_new_kind_keeps_its_values(
        self, db: InfrahubDatabase, target_branch: Branch, rename_data: RenameData
    ) -> None:
        def rename_nickname_and_make_it_long_text(car_schema: NodeSchema) -> None:
            nickname = car_schema.get_attribute(name="nickname")
            nickname.name = "alias"
            nickname.kind = "TextArea"

        await _load_car_change(
            db=db,
            branch=target_branch,
            change_car=rename_nickname_and_make_it_long_text,
            expected_migration_names=["attribute.kind.update", "attribute.name.update"],
        )

        cars = await NodeManager.query(
            db=db, branch=target_branch, schema="TestCar", filters={"alias__value": "speedy"}
        )
        assert [car.id for car in cars] == [rename_data.car]
        for node_id in (rename_data.car, rename_data.car_profile, rename_data.car_template):
            assert await _active_value_labels(db=db, node_id=node_id, attribute_name="alias", branch=target_branch) == [
                ["AttributeValue"]
            ]
        await verify_graph(db=db, kinds=["TestCar", "ProfileTestCar", "TemplateTestCar"])

    async def test_an_attribute_renamed_out_of_a_uniqueness_constraint_is_added_to_the_profiles(
        self, db: InfrahubDatabase, target_branch: Branch, rename_data: RenameData
    ) -> None:
        def rename_plate_out_of_the_constraint(car_schema: NodeSchema) -> None:
            car_schema.get_attribute(name="plate").name = "registration"
            car_schema.uniqueness_constraints.remove(["plate__value", "name__value"])

        await _load_car_change(
            db=db,
            branch=target_branch,
            change_car=rename_plate_out_of_the_constraint,
            expected_migration_names=["attribute.name.update", "node.uniqueness_constraints.update"],
        )

        active = RelationshipStatus.ACTIVE.value
        for node_label, node_id in (
            ("ProfileTestCar", rename_data.car_profile),
            ("TemplateTestCar", rename_data.car_template),
            ("TestCar", rename_data.car),
        ):
            assert await _open_attribute_edge_statuses(
                db=db, node_label=node_label, attribute_name="registration", branch_name=target_branch.name
            ) == {node_id: ([active], [active])}
        await verify_graph(db=db, kinds=["TestCar", "ProfileTestCar", "TemplateTestCar"])

    async def test_an_attribute_renamed_with_a_new_kind_while_its_node_kind_is_renamed_keeps_its_values(
        self, db: InfrahubDatabase, target_branch: Branch, rename_data: RenameData
    ) -> None:
        def rename_truck_kind_and_cargo(candidate: SchemaBranch) -> None:
            truck_schema = candidate.get_node(name="TestTruck")
            candidate.delete(name="TestTruck")
            truck_schema.name = "Lorry"
            cargo = truck_schema.get_attribute(name="cargo")
            cargo.name = "load"
            cargo.kind = "TextArea"
            candidate.set(name="TestLorry", schema=truck_schema)

        await _load_change(
            db=db,
            branch=target_branch,
            change_schema=rename_truck_kind_and_cargo,
            expected_migration_names=["attribute.kind.update", "attribute.name.update", "node.name.update"],
        )

        lorries = await NodeManager.query(
            db=db, branch=target_branch, schema="TestLorry", filters={"load__value": "gravel"}
        )
        assert [lorry.id for lorry in lorries] == [rename_data.truck]
        for node_id in (rename_data.truck, rename_data.truck_profile, rename_data.truck_template):
            assert await _active_value_labels(db=db, node_id=node_id, attribute_name="load", branch=target_branch) == [
                ["AttributeValue"]
            ]
        await verify_graph(db=db, kinds=["TestLorry", "ProfileTestLorry", "TemplateTestLorry"])

    async def test_a_relationship_removed_while_its_node_kind_is_renamed_leaves_the_node(
        self, db: InfrahubDatabase, target_branch: Branch, rename_data: RenameData
    ) -> None:
        identifier = "testtrailer__towed_by"

        def rename_trailer_kind_and_remove_towed_by(candidate: SchemaBranch) -> None:
            trailer_schema = candidate.get_node(name="TestTrailer")
            candidate.delete(name="TestTrailer")
            trailer_schema.name = "Caravan"
            trailer_schema.relationships = [rel for rel in trailer_schema.relationships if rel.name != "towed_by"]
            candidate.set(name="TestCaravan", schema=trailer_schema)
            person_schema = candidate.get_node(name="TestPerson")
            person_schema.relationships = [rel for rel in person_schema.relationships if rel.name != "trailers"]
            candidate.set(name="TestPerson", schema=person_schema)

        await _load_change(
            db=db,
            branch=target_branch,
            change_schema=rename_trailer_kind_and_remove_towed_by,
            expected_migration_names=["node.name.update", "node.relationship.remove", "node.relationship.remove"],
        )

        assert await _open_relationship_edge_statuses(
            db=db, node_id=rename_data.trailer, identifier=identifier, branch=target_branch
        ) == [RelationshipStatus.DELETED.value]
        await verify_graph(
            db=db,
            kinds=[
                "TestCaravan",
                "TestPerson",
                "ProfileTestCaravan",
                "ProfileTestPerson",
                "TemplateTestCaravan",
                "TemplateTestPerson",
            ],
        )
