from unittest.mock import patch

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.node import Node
from infrahub.core.node.constraints.grouped_uniqueness import NodeGroupedUniquenessConstraint
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import HFIDViolatedError, ValidationError
from tests.node_creation import create_and_save


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

    async def test_uniqueness_constraint_single_element_constraints(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_simple
    ):
        p1 = await Node.init(db=db, schema="TestPerson")
        await p1.new(db=db, name="John", height=180)
        await p1.save(db=db)
        p2 = await Node.init(db=db, schema="TestPerson")
        await p2.new(db=db, name="Jane", height=170)
        await p2.save(db=db)
        p3 = await Node.init(db=db, schema="TestPerson")
        await p3.new(db=db, name="Jake", height=175)
        await p3.save(db=db)
        c1 = await Node.init(db=db, schema="TestElectricCar")
        await c1.new(db=db, name="volt", nbr_seats=4, nbr_engine=4, owner=p1, previous_owner=p2, color="#111111")
        await c1.save(db=db)
        c2 = await Node.init(db=db, schema="TestElectricCar")
        await c2.new(db=db, name="bolt", nbr_seats=5, nbr_engine=2, owner=p2, previous_owner=p1, color="#222222")
        await c2.save(db=db)

        # TestPerson attribute constraints
        p_test = await Node.init(db=db, schema="TestPerson")
        await p_test.new(db=db, name="Jerm", height=172)
        p_test.get_schema().uniqueness_constraints = [["name"], ["height"]]
        await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)
        p_test.height.value = 170
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'height'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)
        p_test.height.value = 172

        p_test.name.value = p1.name.value
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'name'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)

        # TestElectricCar attribute constraints
        c_test = await Node.init(db=db, schema="TestElectricCar")
        await c_test.new(db=db, name="colt", nbr_seats=6, nbr_engine=3, owner=p3, color="#333333")
        c_test.get_schema().uniqueness_constraints = [["nbr_seats"], ["color"], ["owner"], ["previous_owner"]]
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)

        c_test.nbr_seats.value = 4
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'nbr_seats'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.nbr_seats.value = 6

        c_test.color.value = "#111111"
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'color'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.color.value = "#333333"

        # TestElectricCar relationship constraints
        await c_test.owner.update(db=db, data=p1)
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        await c_test.owner.update(db=db, data=p3)

        await c_test.previous_owner.update(db=db, data=p2)
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'previous_owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        await c_test.previous_owner.update(db=db, data=p3)

    async def test_uniqueness_constraint_multi_element_constraints(
        self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_generics_simple
    ):
        p1 = await Node.init(db=db, schema="TestPerson")
        await p1.new(db=db, name="John", height=180)
        await p1.save(db=db)
        p2 = await Node.init(db=db, schema="TestPerson")
        await p2.new(db=db, name="Jane", height=170)
        await p2.save(db=db)
        p3 = await Node.init(db=db, schema="TestPerson")
        await p3.new(db=db, name="Jake", height=175)
        await p3.save(db=db)
        c1 = await Node.init(db=db, schema="TestElectricCar")
        await c1.new(db=db, name="volt", nbr_seats=1, nbr_engine=2, owner=p1, previous_owner=p2, color="#111111")
        await c1.save(db=db)
        c2 = await Node.init(db=db, schema="TestElectricCar")
        await c2.new(db=db, name="bolt", nbr_seats=2, nbr_engine=3, owner=p2, previous_owner=p3, color="#222222")
        await c2.save(db=db)
        c3 = await Node.init(db=db, schema="TestElectricCar")
        await c3.new(db=db, name="colt", nbr_seats=3, nbr_engine=4, owner=p3, previous_owner=p1, color="#333333")
        await c3.save(db=db)

        # TestPerson attribute constraints
        p_test = await Node.init(db=db, schema="TestPerson")
        await p_test.new(db=db, name="Jerm", height=172)
        p_test.get_schema().uniqueness_constraints = [["name", "height"]]
        await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)
        p_test.height.value = p1.height.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)
        p_test.name.value = p2.name.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)
        p_test.name.value = p1.name.value
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'name-height'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=p_test)

        # TestElectricCar relationship constraints
        c_test = await Node.init(db=db, schema="TestElectricCar")
        c_test_name = "jolt"
        c_test_nbr_seats = 4
        c_test_nbr_engine = 5
        c_test_owner = p3
        c_test_previous_owner = p3
        c_test_color = "#aaaaaa"
        await c_test.new(
            db=db,
            name=c_test_name,
            nbr_seats=c_test_nbr_seats,
            nbr_engine=c_test_nbr_engine,
            owner=c_test_owner,
            previous_owner=c_test_previous_owner,
            color=c_test_color,
        )
        c_test.get_schema().uniqueness_constraints = [
            ["nbr_seats", "color"],  # 1
            ["nbr_seats", "owner"],  # 2
            ["owner", "previous_owner"],  # 3
            ["previous_owner", "color"],  # 4
        ]
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)

        # test constraint 1 nbr_seats-color
        c_test.nbr_seats.value = c1.nbr_seats.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.color.value = c3.color.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.color.value = c1.color.value
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'nbr_seats-color'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.nbr_seats.value = c_test_nbr_seats
        c_test.color.value = c_test_color

        # test constraint 2 nbr_seats-owner
        c_test.nbr_seats.value = c1.nbr_seats.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c3_owner = await c3.owner.get_peer(db=db)
        await c_test.owner.update(db=db, data=c3_owner)
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.nbr_seats.value = c3.nbr_seats.value
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'nbr_seats-owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.nbr_seats.value = c_test_nbr_seats
        await c_test.owner.update(db=db, data=c_test_owner)

        # test constraint 3 owner-previous_owner
        c1_owner = await c1.owner.get_peer(db=db)
        await c_test.owner.update(db=db, data=c1_owner)
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c2_previous_owner = await c2.previous_owner.get_peer(db=db)
        await c_test.previous_owner.update(db=db, data=c2_previous_owner)
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c1_previous_owner = await c1.previous_owner.get_peer(db=db)
        await c_test.previous_owner.update(db=db, data=c1_previous_owner)
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'owner-previous_owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        await c_test.owner.update(db=db, data=c_test_owner)
        await c_test.previous_owner.update(db=db, data=c_test_previous_owner)

        # test constraint 4 previous_owner-color
        await c_test.previous_owner.update(db=db, data=c1_previous_owner)
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        c_test.color.value = c2.color.value
        await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)
        await c_test.previous_owner.update(db=db, data=c2_previous_owner)
        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'previous_owner-color'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=c_test)

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

    async def test_hfid_violated(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_hfid):
        person_john = await create_and_save(db=db, schema="TestPerson", name="John")
        _ = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person_john)
        car_mercedes_2 = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person_john)

        with pytest.raises(HFIDViolatedError, match="Violates uniqueness constraint 'name-owner'"):
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_mercedes_2)

    async def test_subset_hfid_violated(self, db: InfrahubDatabase, default_branch: Branch, car_person_schema_hfid):
        person_john = await create_and_save(db=db, schema="TestPerson", name="John")
        person_maria = await create_and_save(db=db, schema="TestPerson", name="Maria")
        _ = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person_john)
        car_mercedes_of_maria = await create_and_save(db=db, schema="TestCar", name="mercedes", owner=person_maria)

        with pytest.raises(ValidationError, match="Violates uniqueness constraint 'name'") as exc_info:
            await self.__call_system_under_test(db=db, branch=default_branch, node=car_mercedes_of_maria)
        assert not isinstance(exc_info.value, HFIDViolatedError), "HFIDViolatedError should not be raised here"
