from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import PathType, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import AttributeSchema, MainSchemaTypes
from infrahub.core.schema.attribute_parameters import NumberPoolParameters
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.attribute import NodeAttributeAddChecker, NodeAttributeValueMissingValidatorQuery
from infrahub.database import InfrahubDatabase

SCHEMA_PATH = SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind="TestPerson", field_name="nickname")


def _with_nickname(optional: bool = False) -> MainSchemaTypes:
    person_schema = registry.schema.get(name="TestPerson", branch=registry.default_branch).duplicate()
    person_schema.attributes.append(AttributeSchema(name="nickname", kind="Text", optional=optional))
    return person_schema


def _node_path(branch: Branch, node: Node) -> DataPath:
    return DataPath(branch=branch.name, path_type=PathType.NODE, node_id=node.id, kind="TestPerson")


async def _missing_value_paths(
    db: InfrahubDatabase, branch: Branch, node_schema: MainSchemaTypes, is_isolated: bool
) -> list[DataPath]:
    query = await NodeAttributeValueMissingValidatorQuery.init(
        db=db, branch=branch, node_schema=node_schema, schema_path=SCHEMA_PATH, is_isolated=is_isolated
    )
    await query.execute(db=db)
    return (await query.get_paths()).get_all_data_paths()


async def test_query_finds_every_node_before_the_attribute_exists(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, person_jane_main: Node
) -> None:
    paths = await _missing_value_paths(db=db, branch=default_branch, node_schema=_with_nickname(), is_isolated=True)

    assert len(paths) == 2
    assert {path.node_id: path for path in paths} == {
        person.id: _node_path(branch=default_branch, node=person) for person in (person_john_main, person_jane_main)
    }


async def test_query_on_branch_skips_nodes_with_a_value_and_deleted_nodes(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, person_jane_main: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-with-nickname")
    registry.schema.set(name="TestPerson", schema=_with_nickname(optional=True), branch=branch.name)

    with_value = await Node.init(db=db, schema="TestPerson", branch=branch)
    await with_value.new(db=db, name="Has nickname", nickname="nick")
    await with_value.save(db=db)
    null_value = await Node.init(db=db, schema="TestPerson", branch=branch)
    await null_value.new(db=db, name="Null nickname")
    await null_value.save(db=db)
    jane = await NodeManager.get_one(db=db, id=person_jane_main.id, branch=branch)
    await jane.delete(db=db)

    paths = await _missing_value_paths(db=db, branch=branch, node_schema=_with_nickname(), is_isolated=False)

    assert len(paths) == 2
    assert {path.node_id: path for path in paths} == {
        person_john_main.id: _node_path(branch=default_branch, node=person_john_main),
        null_value.id: _node_path(branch=branch, node=null_value),
    }


@dataclass(frozen=True)
class ViewCase:
    name: str
    is_isolated: bool
    expected_nodes: list[str]


VIEW_CASES = [
    ViewCase(name="branch-view", is_isolated=True, expected_nodes=["deleted_on_main_after_branch"]),
    ViewCase(name="merge-view", is_isolated=False, expected_nodes=["created_on_main_after_branch"]),
]


@pytest.mark.parametrize("case", VIEW_CASES, ids=lambda case: case.name)
async def test_validator_on_branch_reads_the_requested_view_of_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, case: ViewCase
) -> None:
    deleted_on_main_after_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await deleted_on_main_after_branch.new(db=db, name="Deleted on main after branch")
    await deleted_on_main_after_branch.save(db=db)
    branch = await create_branch(db=db, branch_name="branch-before-person")
    await deleted_on_main_after_branch.delete(db=db)
    created_on_main_after_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await created_on_main_after_branch.new(db=db, name="Created on main after branch")
    await created_on_main_after_branch.save(db=db)
    nodes = {
        "deleted_on_main_after_branch": deleted_on_main_after_branch,
        "created_on_main_after_branch": created_on_main_after_branch,
    }

    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.attribute.add",
        node_schema=_with_nickname(),
        schema_path=SCHEMA_PATH,
        schema_branch=SchemaBranch(cache={}, name="test"),
        is_isolated=case.is_isolated,
    )

    grouped_data_paths = await NodeAttributeAddChecker(db=db, branch=branch).check(request)

    assert len(grouped_data_paths) == 1
    assert grouped_data_paths[0].get_all_data_paths() == [
        _node_path(branch=default_branch, node=nodes[label]) for label in case.expected_nodes
    ]


@pytest.mark.parametrize("is_isolated", [True, False], ids=["branch-view", "merge-view"])
async def test_number_pool_size_is_checked_against_the_nodes_of_the_requested_view_of_main(
    db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch, is_isolated: bool
) -> None:
    created_before_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await created_before_branch.new(db=db, name="Created before branch")
    await created_before_branch.save(db=db)
    branch = await create_branch(db=db, branch_name="branch-before-person")
    created_on_main_after_branch = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await created_on_main_after_branch.new(db=db, name="Created on main after branch")
    await created_on_main_after_branch.save(db=db)

    person_schema = registry.schema.get(name="TestPerson", branch=registry.default_branch).duplicate()
    person_schema.attributes.append(
        AttributeSchema(
            name="nickname",
            kind="NumberPool",
            optional=False,
            parameters=NumberPoolParameters(start_range=1, end_range=1),
        )
    )
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.attribute.add",
        node_schema=person_schema,
        schema_path=SCHEMA_PATH,
        schema_branch=SchemaBranch(cache={}, name="test"),
        is_isolated=is_isolated,
    )
    checker = NodeAttributeAddChecker(db=db, branch=branch)

    if is_isolated:
        assert await checker.check(request) == []
    else:
        with pytest.raises(
            ValueError, match=r"^The size of the NumberPool is smaller than the number of existing nodes 1 < 2\.$"
        ):
            await checker.check(request)
