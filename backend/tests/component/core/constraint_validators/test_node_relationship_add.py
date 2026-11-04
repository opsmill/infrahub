from dataclasses import dataclass

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import BranchSupportType, PathType, RelationshipCardinality, SchemaPathType
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.path import DataPath, SchemaPath
from infrahub.core.schema import MainSchemaTypes, RelationshipSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.node.relationship import NodeRelationshipAddChecker
from infrahub.database import InfrahubDatabase

SCHEMA_PATH = SchemaPath(path_type=SchemaPathType.RELATIONSHIP, schema_kind="TestCar", field_name="inspectors")


def _with_inspectors(optional: bool = False) -> MainSchemaTypes:
    car_schema = registry.schema.get(name="TestCar", branch=registry.default_branch).duplicate()
    car_schema.relationships.append(
        RelationshipSchema(
            name="inspectors",
            peer="TestPerson",
            cardinality=RelationshipCardinality.MANY,
            optional=optional,
            identifier="car__inspectors",
            branch=BranchSupportType.AWARE,
        )
    )
    return car_schema


def _node_path(branch: Branch, node: Node) -> DataPath:
    return DataPath(branch=branch.name, path_type=PathType.NODE, node_id=node.id, kind="TestCar")


async def _create_car(
    db: InfrahubDatabase, branch: Branch, name: str, owner: Node, inspectors: list[Node] | None = None
) -> Node:
    car = await Node.init(db=db, schema="TestCar", branch=branch)
    if inspectors:
        await car.new(db=db, name=name, owner=owner.id, inspectors=[inspector.id for inspector in inspectors])
    else:
        await car.new(db=db, name=name, owner=owner.id)
    await car.save(db=db)
    return car


async def _check(db: InfrahubDatabase, branch: Branch, is_isolated: bool) -> list[DataPath]:
    request = SchemaConstraintValidatorRequest(
        branch=branch,
        constraint_name="node.relationship.add",
        node_schema=_with_inspectors(),
        schema_path=SCHEMA_PATH,
        schema_branch=SchemaBranch(cache={}, name="test"),
        is_isolated=is_isolated,
    )
    grouped_data_paths = await NodeRelationshipAddChecker(db=db, branch=branch).check(request)
    assert len(grouped_data_paths) == 1
    return grouped_data_paths[0].get_all_data_paths()


@pytest.mark.parametrize("is_isolated", [True, False], ids=["branch-view", "merge-view"])
async def test_check_accepts_branch_nodes_that_set_the_new_relationship(
    db: InfrahubDatabase,
    default_branch: Branch,
    person_john_main: Node,
    person_jane_main: Node,
    is_isolated: bool,
) -> None:
    branch = await create_branch(db=db, branch_name="branch-with-inspectors")
    registry.schema.set(name="TestCar", schema=_with_inspectors(), branch=branch.name)
    await _create_car(db=db, branch=branch, name="accord", owner=person_john_main, inspectors=[person_john_main])
    await _create_car(
        db=db, branch=branch, name="volt", owner=person_john_main, inspectors=[person_jane_main, person_john_main]
    )

    assert await _check(db=db, branch=branch, is_isolated=is_isolated) == []


@dataclass(frozen=True)
class ViewCase:
    name: str
    is_isolated: bool
    expected_nodes: list[str]


VIEW_CASES = [
    ViewCase(
        name="branch-view",
        is_isolated=True,
        expected_nodes=["created_on_main_before_branch", "deleted_on_main_after_branch", "created_on_branch_without"],
    ),
    ViewCase(
        name="merge-view",
        is_isolated=False,
        expected_nodes=["created_on_main_before_branch", "created_on_main_after_branch", "created_on_branch_without"],
    ),
]


@pytest.mark.parametrize("case", VIEW_CASES, ids=lambda case: case.name)
async def test_check_on_branch_flags_nodes_without_the_relationship_in_the_requested_view_of_main(
    db: InfrahubDatabase, default_branch: Branch, person_john_main: Node, case: ViewCase
) -> None:
    created_on_main_before_branch = await _create_car(
        db=db, branch=default_branch, name="before", owner=person_john_main
    )
    deleted_on_main_after_branch = await _create_car(
        db=db, branch=default_branch, name="deleted", owner=person_john_main
    )
    branch = await create_branch(db=db, branch_name="branch-with-inspectors")
    await deleted_on_main_after_branch.delete(db=db)
    created_on_main_after_branch = await _create_car(db=db, branch=default_branch, name="after", owner=person_john_main)

    registry.schema.set(name="TestCar", schema=_with_inspectors(optional=True), branch=branch.name)
    await _create_car(db=db, branch=branch, name="with", owner=person_john_main, inspectors=[person_john_main])
    created_on_branch_without = await _create_car(db=db, branch=branch, name="without", owner=person_john_main)
    nodes = {
        "created_on_main_before_branch": (default_branch, created_on_main_before_branch),
        "deleted_on_main_after_branch": (default_branch, deleted_on_main_after_branch),
        "created_on_main_after_branch": (default_branch, created_on_main_after_branch),
        "created_on_branch_without": (branch, created_on_branch_without),
    }

    paths = await _check(db=db, branch=branch, is_isolated=case.is_isolated)

    assert len(paths) == len(case.expected_nodes)
    assert {path.node_id: path for path in paths} == {
        nodes[label][1].id: _node_path(branch=nodes[label][0], node=nodes[label][1]) for label in case.expected_nodes
    }
