import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.migrations.schema.node_kind_update import NodeKindUpdateMigration
from infrahub.core.migrations.shared import MigrationInput
from infrahub.core.node import Node
from infrahub.core.path import SchemaPath
from infrahub.core.schema import AttributeSchema, MainSchemaTypes, NodeSchema, SchemaRoot
from infrahub.core.schema.basenode_schema import SchemaAttributePath
from infrahub.core.validators.uniqueness.query import (
    TargetedUniquenessValidationQuery,
    TargetedUniquenessViolation,
)
from infrahub.database import InfrahubDatabase


def _attr_element(schema: MainSchemaTypes, name: str) -> SchemaAttributePath:
    return SchemaAttributePath(attribute_schema=schema.get_attribute(name))


def _rel_element(schema: MainSchemaTypes, name: str) -> SchemaAttributePath:
    return SchemaAttributePath(relationship_schema=schema.get_relationship(name))


async def _run_query(
    db: InfrahubDatabase,
    branch: Branch,
    kind: str,
    constraint_elements: list[SchemaAttributePath],
    node_uuids: list[str],
) -> list[TargetedUniquenessViolation]:
    query = await TargetedUniquenessValidationQuery.init(
        db=db, branch=branch, kind=kind, constraint_elements=constraint_elements, node_uuids=node_uuids
    )
    await query.execute(db=db)
    return list(query.get_data())


async def _update_car(db: InfrahubDatabase, branch: Branch, car_id: str, **attribute_values: object) -> None:
    car = await NodeManager.get_one(id=car_id, db=db, branch=branch)
    for name, value in attribute_values.items():
        car.get_attribute(name).value = value
    await car.save(db=db)


async def _migrate_car_kind_on_branch(db: InfrahubDatabase, default_branch: Branch, branch: Branch) -> MainSchemaTypes:
    """Migrate the whole TestCar kind to Test2NewCar on the branch and return the new schema.

    The migration results in multiple Node vertices with the same UUID, a case that can be difficult
    to handle correctly.
    """
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    new_car_schema = schema_branch.get_node(name="TestCar")
    new_car_schema.name = "NewCar"
    new_car_schema.namespace = "Test2"
    registry.schema.set(name="Test2NewCar", schema=new_car_schema, branch=branch.name)
    migration = NodeKindUpdateMigration(
        previous_node_schema=schema_branch.get(name="TestCar"),
        new_node_schema=new_car_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="Test2NewCar", field_name="namespace"),
    )
    execution_result = await migration.execute(migration_input=MigrationInput(db=db), branch=branch)
    assert not execution_result.errors
    return new_car_schema


class TestTargetedUniquenessQuery:
    async def test_batched_mixed_colliding_and_unique(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
        car_yaris_main: Node,
        branch: Branch,
    ) -> None:
        # accord shares nbr_seats=5 with the untouched prius and camry; volt is made unique
        await _update_car(db, branch, car_volt_main.id, nbr_seats=2)
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(
            db, branch, "TestCar", [_attr_element(schema, "nbr_seats")], [car_accord_main.id, car_volt_main.id]
        )

        assert len(violations) == 1
        violation = violations[0]
        assert violation.changed_uuid == car_accord_main.id
        assert violation.element_values == (5,)
        assert set(violation.partner_uuids) == {car_prius_main.id, car_camry_main.id}

    async def test_multi_field_matches_full_tuple_only(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
        car_yaris_main: Node,
        branch: Branch,
    ) -> None:
        # pairwise overlap on single elements but no shared full tuple: accord(5, red),
        # prius(5, blue), volt(4, blue); camry and yaris are moved out of the way
        await _update_car(db, branch, car_accord_main.id, nbr_seats=5, color="#ff0000")
        await _update_car(db, branch, car_prius_main.id, nbr_seats=5, color="#0000ff")
        await _update_car(db, branch, car_volt_main.id, nbr_seats=4, color="#0000ff")
        await _update_car(db, branch, car_camry_main.id, nbr_seats=9)
        await _update_car(db, branch, car_yaris_main.id, nbr_seats=8)
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_attr_element(schema, "nbr_seats"), _attr_element(schema, "color")]
        changed = [car_accord_main.id, car_prius_main.id, car_volt_main.id]

        violations = await _run_query(db, branch, "TestCar", elements, changed)

        assert violations == []

        # completing the tuple match flags exactly the two matching cars
        await _update_car(db, branch, car_prius_main.id, color="#ff0000")

        violations = await _run_query(db, branch, "TestCar", elements, changed)

        assert {v.changed_uuid for v in violations} == {car_accord_main.id, car_prius_main.id}
        by_changed = {v.changed_uuid: v for v in violations}
        assert by_changed[car_accord_main.id].partner_uuids == (car_prius_main.id,)
        assert by_changed[car_prius_main.id].partner_uuids == (car_accord_main.id,)
        assert by_changed[car_accord_main.id].element_values == (5, "#ff0000")

    async def test_multi_field_group_with_relationship_element(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        person_john_main: Node,
        person_jane_main: Node,
        branch: Branch,
    ) -> None:
        # accord and prius share owner john AND nbr_seats=5; camry has the same seats but a
        # different owner, so it must not match the tuple
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_rel_element(schema, "owner"), _attr_element(schema, "nbr_seats")]

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_accord_main.id
        assert violations[0].partner_uuids == (car_prius_main.id,)
        assert violations[0].element_values == (person_john_main.id, 5)

        # same owner but different seats no longer matches
        await _update_car(db, branch, car_prius_main.id, nbr_seats=7)

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert violations == []

    async def test_composite_group_narrows_with_a_conjunctive_prefilter(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        car_person_schema: object,
    ) -> None:
        """Every constraint element must be required up front, before any per-candidate work."""
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_rel_element(schema, "owner"), _attr_element(schema, "nbr_seats")]

        query = await TargetedUniquenessValidationQuery.init(
            db=db,
            branch=branch,
            kind="TestCar",
            constraint_elements=elements,
            node_uuids=["changed-car"],
        )
        rendered_query = query.get_query()

        # both elements are required by the single narrowing step ...
        assert "(:Relationship {name: $rel_identifier_0})" in rendered_query
        assert "(:Node {uuid: value_0})" in rendered_query
        assert (
            "MATCH (candidate)-[:HAS_ATTRIBUTE]->(:Attribute {name: $attr_name_1})"
            "-[:HAS_VALUE]->(:AttributeValueIndexed {value: value_1})" in rendered_query
        )
        # ... and no element is singled out as a population-wide anchor
        assert "anchor_peer" not in rendered_query
        # candidates are never collected as nodes, only their uuids at the end
        assert "collect(DISTINCT candidate)" not in rendered_query
        assert "collect(DISTINCT candidate.uuid) AS partner_uuids" in rendered_query

    async def test_prefilter_is_independent_of_element_order(
        self,
        db: InfrahubDatabase,
        branch: Branch,
        car_person_schema: object,
    ) -> None:
        """Reordering a constraint group must not change which element the query leads with."""
        schema = registry.schema.get("TestCar", branch=branch)
        owner = _rel_element(schema, "owner")
        seats = _attr_element(schema, "nbr_seats")

        rendered = []
        for elements in ([owner, seats], [seats, owner]):
            query = await TargetedUniquenessValidationQuery.init(
                db=db,
                branch=branch,
                kind="TestCar",
                constraint_elements=elements,
                node_uuids=["changed-car"],
            )
            rendered.append(query.get_query())

        for text in rendered:
            # exactly one narrowing step, and no element promoted to a population-wide anchor
            assert text.count("WITH DISTINCT candidate") == 1
            assert "anchor_peer" not in text
            # both elements are required by that step, whichever order they were declared in
            assert "(:Relationship {name: $rel_identifier_" in text
            assert "(:AttributeValueIndexed {value: value_" in text

    async def test_relationship_only_collision_and_missing_peer(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
        person_john_main: Node,
        branch: Branch,
    ) -> None:
        # driver is an optional cardinality-one relationship: accord and camry are given the same
        # driver, volt has none
        for car_id in (car_accord_main.id, car_camry_main.id):
            car = await NodeManager.get_one(id=car_id, db=db, branch=branch)
            await car.get_relationship("driver").update(data=person_john_main, db=db)
            await car.save(db=db)
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_rel_element(schema, "driver")]

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_accord_main.id
        assert violations[0].partner_uuids == (car_camry_main.id,)
        assert violations[0].element_values == (person_john_main.id,)

        # a changed node without a live peer contributes no value and cannot collide
        violations = await _run_query(db, branch, "TestCar", elements, [car_volt_main.id])

        assert violations == []

    async def test_null_attribute_values_collide(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        person_john_main: Node,
        branch: Branch,
    ) -> None:
        # two cars without nbr_seats store the null sentinel and must still collide
        car_a = await Node.init(db=db, schema="TestCar", branch=branch)
        await car_a.new(db=db, name="nullseats-a", owner=person_john_main.id)
        await car_a.save(db=db)
        car_b = await Node.init(db=db, schema="TestCar", branch=branch)
        await car_b.new(db=db, name="nullseats-b", owner=person_john_main.id)
        await car_b.save(db=db)
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(db, branch, "TestCar", [_attr_element(schema, "nbr_seats")], [car_a.id])

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_a.id
        assert violations[0].partner_uuids == (car_b.id,)
        assert violations[0].element_values == ("NULL",)

    async def test_enum_attribute_collision_uses_stored_value(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_camry_main: Node,
        car_prius_main: Node,
        branch: Branch,
    ) -> None:
        await _update_car(db, branch, car_accord_main.id, transmission="manual")
        await _update_car(db, branch, car_camry_main.id, transmission="manual")
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(
            db, branch, "TestCar", [_attr_element(schema, "transmission")], [car_accord_main.id]
        )

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_accord_main.id
        assert violations[0].partner_uuids == (car_camry_main.id,)
        assert violations[0].element_values == ("manual",)

    async def test_large_attribute_type_validated(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: object,
    ) -> None:
        schema_root = SchemaRoot(
            nodes=[
                NodeSchema(
                    name="Document",
                    namespace="Test",
                    attributes=[
                        AttributeSchema(name="name", kind="Text"),
                        AttributeSchema(name="content", kind="TextArea", optional=True),
                    ],
                )
            ]
        )
        registry.schema.register_schema(schema=schema_root, branch=default_branch.name)
        shared_content = "lorem ipsum " * 50
        doc_a = await Node.init(db=db, schema="TestDocument", branch=default_branch)
        await doc_a.new(db=db, name="doc-a", content=shared_content)
        await doc_a.save(db=db)
        doc_b = await Node.init(db=db, schema="TestDocument", branch=default_branch)
        await doc_b.new(db=db, name="doc-b", content=shared_content)
        await doc_b.save(db=db)
        schema = registry.schema.get("TestDocument", branch=default_branch)

        # a large-type attribute has no value index but is still validated
        violations = await _run_query(
            db, default_branch, "TestDocument", [_attr_element(schema, "content")], [doc_a.id]
        )

        assert len(violations) == 1
        assert violations[0].partner_uuids == (doc_b.id,)

        # in a multi-element group the full tuple must match: shared content but distinct names
        elements = [_attr_element(schema, "content"), _attr_element(schema, "name")]

        violations = await _run_query(db, default_branch, "TestDocument", elements, [doc_a.id])

        assert violations == []

        # a third document sharing both content and name completes the tuple
        doc_c = await Node.init(db=db, schema="TestDocument", branch=default_branch)
        await doc_c.new(db=db, name="doc-a", content=shared_content)
        await doc_c.save(db=db)

        violations = await _run_query(db, default_branch, "TestDocument", elements, [doc_a.id])

        assert len(violations) == 1
        assert violations[0].partner_uuids == (doc_c.id,)
        assert violations[0].element_values == (shared_content, "doc-a")

    async def test_post_fork_updates_on_main_and_branch(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        default_branch: Branch,
        branch: Branch,
    ) -> None:
        # accord, prius and camry all share nbr_seats=5 when the branch forks; both partners then
        # get distinct values on main, which the branch must see: the collision is gone
        await _update_car(db, default_branch, car_prius_main.id, nbr_seats=8)
        await _update_car(db, default_branch, car_camry_main.id, nbr_seats=9)
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_attr_element(schema, "nbr_seats")]

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert violations == []

        # camry then gets a new value on main and accord the same new value on the branch; the
        # two non-conflicting updates must collide across branches
        await _update_car(db, default_branch, car_camry_main.id, nbr_seats=7)
        await _update_car(db, branch, car_accord_main.id, nbr_seats=7)

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert violations[0].partner_uuids == (car_camry_main.id,)
        assert violations[0].element_values == (7,)

        # the same collision is found when the main-updated node is the changed one
        violations = await _run_query(db, branch, "TestCar", elements, [car_camry_main.id])

        assert len(violations) == 1
        assert violations[0].partner_uuids == (car_accord_main.id,)

    async def test_branch_visibility(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        branch: Branch,
    ) -> None:
        schema = registry.schema.get("TestCar", branch=branch)
        elements = [_attr_element(schema, "nbr_seats")]

        # data created on main only is visible from the branch
        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert set(violations[0].partner_uuids) == {car_prius_main.id, car_camry_main.id}

        # the branch-local value overrides main and no longer collides
        await _update_car(db, branch, car_accord_main.id, nbr_seats=6)

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert violations == []

        # two branch-local values collide with each other
        await _update_car(db, branch, car_camry_main.id, nbr_seats=6)

        violations = await _run_query(db, branch, "TestCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert violations[0].partner_uuids == (car_camry_main.id,)
        assert violations[0].element_values == (6,)

    async def test_partner_deleted_on_branch_is_ignored(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        branch: Branch,
    ) -> None:
        # accord, prius and camry share nbr_seats=5 on main, but both partners are deleted on the
        # branch, so the branch-level deletion overrides the value they still hold on main
        for car_id in (car_prius_main.id, car_camry_main.id):
            car = await NodeManager.get_one(id=car_id, db=db, branch=branch)
            await car.delete(db=db)
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(db, branch, "TestCar", [_attr_element(schema, "nbr_seats")], [car_accord_main.id])

        assert violations == []

    async def test_changed_node_deleted_on_branch_is_ignored(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        branch: Branch,
    ) -> None:
        # a node in the changed set was deleted on the branch: the value it still holds on main
        # must not be used, even though prius and camry still share it
        car = await NodeManager.get_one(id=car_accord_main.id, db=db, branch=branch)
        await car.delete(db=db)
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(db, branch, "TestCar", [_attr_element(schema, "nbr_seats")], [car_accord_main.id])

        assert violations == []

    async def test_changed_nodes_collide_with_each_other(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        branch: Branch,
    ) -> None:
        # only accord and prius keep nbr_seats=5; both are changed and must report each other
        await _update_car(db, branch, car_camry_main.id, nbr_seats=9)
        schema = registry.schema.get("TestCar", branch=branch)

        violations = await _run_query(
            db, branch, "TestCar", [_attr_element(schema, "nbr_seats")], [car_accord_main.id, car_prius_main.id]
        )

        by_changed = {v.changed_uuid: v for v in violations}
        assert set(by_changed) == {car_accord_main.id, car_prius_main.id}
        assert by_changed[car_accord_main.id].partner_uuids == (car_prius_main.id,)
        assert by_changed[car_prius_main.id].partner_uuids == (car_accord_main.id,)

    async def test_same_uuid_duplicate_from_kind_migration(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        car_prius_main: Node,
        car_camry_main: Node,
        default_branch: Branch,
    ) -> None:
        # accord, prius, and camry all share nbr_seats=5
        migration_branch = await create_branch(db=db, branch_name="kind-migration-branch")
        new_car_schema = await _migrate_car_kind_on_branch(
            db=db, default_branch=default_branch, branch=migration_branch
        )

        # the branch accord moves to 9 after the migration; still 5 on default branch
        migrated_accord = await NodeManager.get_one(db=db, branch=migration_branch, id=car_accord_main.id)
        migrated_accord.get_attribute("nbr_seats").value = 9
        await migrated_accord.save(db=db)

        elements = [_attr_element(new_car_schema, "nbr_seats")]

        # updated value on branch is accepted as unique following the migration
        violations = await _run_query(db, migration_branch, "Test2NewCar", elements, [car_accord_main.id])

        assert violations == []

        # camry and prius (both nbr_seats=5) collide. accord does not.
        violations = await _run_query(db, migration_branch, "Test2NewCar", elements, [car_camry_main.id])

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_camry_main.id
        assert violations[0].partner_uuids == (car_prius_main.id,)
        assert violations[0].element_values == (5,)

        # the stale prius object is then updated on the DEFAULT branch after the migration; the
        # attribute vertices are shared, so the new value must be visible through prius's live
        # vertex on the migration branch and now collide with the branch-updated accord (9)
        await _update_car(db, default_branch, car_prius_main.id, nbr_seats=9)

        violations = await _run_query(db, migration_branch, "Test2NewCar", elements, [car_accord_main.id])

        assert len(violations) == 1
        assert violations[0].changed_uuid == car_accord_main.id
        assert violations[0].partner_uuids == (car_prius_main.id,)
        assert violations[0].element_values == (9,)

        # and camry (still 5) has lost its only partner: prius's superseded value-5 edge on the
        # default branch must not still count for it
        violations = await _run_query(db, migration_branch, "Test2NewCar", elements, [car_camry_main.id])

        assert violations == []

    async def test_peer_attribute_element_rejected(
        self,
        db: InfrahubDatabase,
        car_accord_main: Node,
        branch: Branch,
    ) -> None:
        car_schema = registry.schema.get("TestCar", branch=branch)
        person_schema = registry.schema.get_node_schema("TestPerson", branch=branch)
        peer_attribute_element = SchemaAttributePath(
            relationship_schema=car_schema.get_relationship("owner"),
            related_schema=person_schema,
            attribute_schema=person_schema.get_attribute("height"),
        )

        with pytest.raises(
            ValueError,
            match=(
                r"^owner__height is not supported for a targeted uniqueness check: "
                r"attributes of related peers cannot be part of a uniqueness constraint$"
            ),
        ):
            await TargetedUniquenessValidationQuery.init(
                db=db,
                branch=branch,
                kind="TestCar",
                constraint_elements=[peer_attribute_element],
                node_uuids=[car_accord_main.id],
            )

    async def test_generic_kind_finds_collisions_across_implementations(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_generics_data_simple: dict[str, Node],
    ) -> None:
        # all three cars (two TestElectricCar, one TestGazCar) share nbr_seats=4; the query is
        # anchored on the generic kind and one changed implementing node
        data = car_person_generics_data_simple
        schema = registry.schema.get("TestCar", branch=default_branch)

        violations = await _run_query(
            db, default_branch, "TestCar", [_attr_element(schema, "nbr_seats")], [data["c1"].id]
        )

        assert len(violations) == 1
        assert violations[0].changed_uuid == data["c1"].id
        assert set(violations[0].partner_uuids) == {data["c2"].id, data["c3"].id}
        assert violations[0].element_values == (4,)
