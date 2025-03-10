from unittest.mock import patch

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError


class TestNodeGroupedUniquenessConstraint:
    async def __call_system_under_test(self, db, branch, node, filters=None):
        constraint = NodeGroupedUniquenessConstraint(db=db, branch=branch)
        await constraint.check(node=node, filters=filters)

    async def test_no_uniqueness_constraint(
        self, db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
    ):
        await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_no_conflicts(
        self, db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
    ):
        car_accord_main.get_schema().uniqueness_constraints = [["name__value"]]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_conflict_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
    ):
        car_accord_main.name.value = "camry"
        car_accord_main.get_schema().uniqueness_constraints = [["name__value"]]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'name'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_conflict_attribute_with_null(
        self, db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
    ):
        # this change is allowed
        car_camry_main.color.value = None
        await self.__call_system_under_test(db=db, branch=default_branch, node=car_camry_main)

        await car_camry_main.save(db=db)
        # this change is blocked
        car_accord_main.color.value = None
        car_accord_main.get_schema().uniqueness_constraints = [["color__value"]]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'color'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_filters(
        self, db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_camry_main: Node
    ):
        car_accord_main.name.value = "camry"
        car_accord_main.get_schema().uniqueness_constraints = [
            ["name__value"],
            ["owner", "color__value"],
            ["nbr_seats__value", "owner"],
        ]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main, filters=["color"])

    async def test_uniqueness_constraint_no_conflict_two_attribute(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
    ):
        car_accord_main.get_schema().uniqueness_constraints = [["name__value", "color__value"]]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_conflict_two_attribute(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
    ):
        car_accord_main.name.value = "camry"
        car_accord_main.get_schema().uniqueness_constraints = [
            ["name__value", "color__value"],
            ["nbr_seats__value", "name__value"],
        ]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'name-color'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_no_conflict_attribute_enum(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
    ):
        car_schema = registry.schema.get("TestCar", branch=default_branch, duplicate=False)
        car_schema.uniqueness_constraints = [["nbr_seats__value", "name__value"]]
        attr = car_schema.get_attribute("nbr_seats")
        attr.optional = False
        attr.enum = [2, 4, 5, 7]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_conflict_attribute_enum(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_accord_main: Node,
        car_camry_main: Node,
        car_volt_main: Node,
    ):
        car_schema = registry.schema.get("TestCar", branch=default_branch, duplicate=False)
        attr = car_schema.get_attribute("nbr_seats")
        attr.optional = False
        attr.enum = [2, 4, 5, 7]

        car_accord_main.name.value = "camry"
        car_accord_main.get_schema().uniqueness_constraints = [["nbr_seats__value", "name__value"]]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'nbr_seats-name'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_accord_main)

    async def test_uniqueness_constraint_no_conflict_one_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_node: Node = car_person_generics_data_simple["c1"]
        car_node.get_schema().uniqueness_constraints = [["previous_owner"]]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_node)

    async def test_uniqueness_constraint_conflict_one_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_node: Node = car_person_generics_data_simple["c1"]
        car_node.get_schema().uniqueness_constraints = [["owner"]]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_node)

    async def test_uniqueness_constraint_no_conflict_two_relationships(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_node: Node = car_person_generics_data_simple["c1"]
        car_node.get_schema().uniqueness_constraints = [["previous_owner", "owner"]]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_node)

    async def test_uniqueness_constraint_no_conflict_two_relationships_with_overlap(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        p1 = car_person_generics_data_simple["p1"]
        p2 = car_person_generics_data_simple["p2"]
        p3 = await Node.init(db=db, schema=registry.schema.get(name="TestPerson"))
        await p3.new(db=db, name="Geoff", height=158)
        await p3.save(db=db)
        car_1: Node = car_person_generics_data_simple["c1"]
        car_2: Node = car_person_generics_data_simple["c2"]
        await car_1.previous_owner.update(db=db, data=p2)
        await car_1.save(db=db)
        await car_2.owner.update(db=db, data=p1)
        await car_2.previous_owner.update(db=db, data=p3)
        await car_2.save(db=db)
        car_3 = await Node.init(db=db, schema=registry.schema.get(name="TestElectricCar"))
        await car_3.new(db=db, name="dolt", nbr_seats=4, nbr_engine=2, owner=p2, previous_owner=p3)
        await car_3.save(db=db)
        car_1.get_schema().uniqueness_constraints = [["previous_owner", "owner"]]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_1)

    async def test_uniqueness_constraint_conflict_two_relationship(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        person_1 = car_person_generics_data_simple["p1"]
        car_node_1: Node = car_person_generics_data_simple["c1"]
        await car_node_1.previous_owner.update(data=person_1, db=db)
        await car_node_1.save(db=db)
        car_node_2: Node = car_person_generics_data_simple["c2"]
        await car_node_2.previous_owner.update(data=person_1, db=db)
        car_node_2.get_schema().uniqueness_constraints = [["previous_owner", "owner"]]

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'previous_owner-owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_node_2)

    async def test_uniqueness_constraint_no_conflict_relationship_and_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_node: Node = car_person_generics_data_simple["c1"]
        car_node.get_schema().uniqueness_constraints = [
            ["nbr_seats__value", "name__value"],
            ["previous_owner", "nbr_seats__value"],
        ]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_node)

    @pytest.mark.parametrize(
        ["node_constraints", "parent_constraints", "node_query_should_run"],
        [
            (
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value"],
                ],
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value"],
                ],
                False,
            ),
            (
                [
                    ["nbr_seats__value", "name__value"],
                ],
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value"],
                ],
                False,
            ),
            (
                [
                    ["previous_owner", "name__value"],
                ],
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value"],
                ],
                True,
            ),
            (
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value", "color__value"],
                ],
                [
                    ["nbr_seats__value", "name__value"],
                    ["previous_owner", "nbr_seats__value"],
                ],
                True,
            ),
        ],
    )
    async def test_uniqueness_constraint_skips_overlapping_constraints(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_generics_data_simple,
        node_constraints: list[list[str]],
        parent_constraints: list[list[str]],
        node_query_should_run: bool,
    ):
        car_node: Node = car_person_generics_data_simple["c1"]
        car_schema = car_node.get_schema()
        schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
        parent_kind = car_schema.inherit_from[0]
        parent_schema = schema_branch.get(name=parent_kind, duplicate=False)
        car_schema.uniqueness_constraints = node_constraints
        parent_schema.uniqueness_constraints = parent_constraints

        # make sure we only use this query once if the constraints overlap
        with patch(
            "infrahub.core.node.constraints.grouped_uniqueness.NodeUniqueAttributeConstraintQuery",
            wraps=NodeUniqueAttributeConstraintQuery,
        ) as wrapped_query:
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_node)
            if node_query_should_run:
                assert len(wrapped_query.init.call_args_list) == 2
            else:
                assert len(wrapped_query.init.call_args_list) == 1
            query_kinds = {init_call[1]["query_request"].kind for init_call in wrapped_query.init.call_args_list}
            if node_query_should_run:
                assert query_kinds == {car_schema.kind, parent_kind}
            else:
                assert query_kinds == {parent_kind}

    async def test_uniqueness_constraint_conflict_relationship_and_attribute(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        person_1 = car_person_generics_data_simple["p1"]
        car_node_1: Node = car_person_generics_data_simple["c1"]
        await car_node_1.previous_owner.update(data=person_1, db=db)
        await car_node_1.save(db=db)
        car_node_2: Node = car_person_generics_data_simple["c2"]
        await car_node_2.previous_owner.update(data=person_1, db=db)
        await car_node_2.save(db=db)
        car_node_3: Node = car_person_generics_data_simple["c3"]
        await car_node_3.previous_owner.update(data=person_1, db=db)
        car_node_3.get_schema().uniqueness_constraints = [
            ["nbr_seats__value", "name__value"],
            ["previous_owner", "nbr_seats__value"],
        ]

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_node_3)

    async def test_generic_constraints_success(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_generic_schema = registry.schema.get("TestCar", branch=default_branch, duplicate=False)
        car_generic_schema.uniqueness_constraints = [["color__value", "owner"]]
        car_node_1: Node = car_person_generics_data_simple["c1"]
        car_node_1.color.value = "#123456"
        await car_node_1.save(db=db)
        car_node_2: Node = car_person_generics_data_simple["c2"]
        car_node_2.color.value = "#654321"
        await car_node_2.save(db=db)
        car_node_3: Node = car_person_generics_data_simple["c3"]
        car_node_3.color.value = "#abcdef"
        await car_node_3.save(db=db)

        await self.__call_system_under_test(db=db, branch=default_branch, node=car_person_generics_data_simple["c1"])

    async def test_generic_constraints_failure(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_generics_data_simple
    ):
        car_generic_schema = registry.schema.get("TestCar", branch=default_branch, duplicate=False)
        car_generic_schema.uniqueness_constraints = [["color__value", "owner"]]
        car_node_1 = car_person_generics_data_simple["c1"]
        person_node_2 = car_person_generics_data_simple["p2"]
        await car_node_1.owner.update(db=db, data=person_node_2)

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'color-owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_node_1)
