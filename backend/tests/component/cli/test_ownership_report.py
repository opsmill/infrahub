import pytest

from infrahub.cli.db_commands.ownership_report import ownership_report
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch
from infrahub.core.node import Node
from infrahub.core.ownership.report import (
    LinkOwnerRow,
    OwnershipReport,
    ProtectedValueRow,
    RepositoryOwnerRow,
    build_ownership_report,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase

# The owner edges of a repository are written as an earlier release stored them, because a repository is refused
# as owner from the upgrade.
ADD_ATTRIBUTE_OWNER = """
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(holder:Attribute {name: "color"})
MATCH (owner:Node {uuid: $owner_id})
CREATE (holder)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at}]->(owner)
"""
ADD_LINK_OWNER = """
MATCH (:Node {uuid: $node_id})-[:IS_RELATED]-(holder:Relationship)
MATCH (owner:Node {uuid: $owner_id})
CREATE (holder)-[:HAS_OWNER {branch: $branch, branch_level: $branch_level, status: "active", from: $at}]->(owner)
"""


async def _add_owner(db: InfrahubDatabase, query: str, branch: Branch, node_id: str, owner_id: str) -> None:
    await db.execute_query(
        query=query,
        params={
            "node_id": node_id,
            "owner_id": owner_id,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": Timestamp().to_string(),
        },
    )


async def _create(db: InfrahubDatabase, kind: str, **data: str) -> Node:
    node = await Node.init(db=db, schema=kind)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


async def _create_car(
    db: InfrahubDatabase,
    name: str,
    person: Node,
    color_owner_id: str | None = None,
    link_owner_id: str | None = None,
    is_protected: bool = False,
) -> Node:
    car = await Node.init(db=db, schema="TestCar")
    await car.new(
        db=db,
        name=name,
        color={"value": "#000000", "owner": color_owner_id, "is_protected": is_protected},
        owner={"id": person.id, "_relation__owner": link_owner_id},
    )
    await car.save(db=db)
    return car


@pytest.fixture
async def repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> Node:
    """Create each case of the report, and the cases that the report leaves out.

    The repository owns the color of two cars on the default branch and of one car on a branch, and one link.
    An account group owns one color and one link. One color is protected. One car has no owner and no protection.
    """
    repository = await _create(
        db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git"
    )
    group = await _create(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    person = await _create(db=db, kind="TestPerson", name="John")

    for name in ("repository-car-1", "repository-car-2"):
        car = await _create_car(db=db, name=name, person=person)
        await _add_owner(
            db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
        )
    await _add_owner(db=db, query=ADD_LINK_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id)
    await _create_car(db=db, name="group-car", person=person, color_owner_id=group.id, link_owner_id=group.id)
    await _create_car(db=db, name="protected-car", person=person, is_protected=True)
    branch_car = await _create_car(db=db, name="plain-car", person=person)
    branch = await create_branch(db=db, branch_name="branch1")
    await _add_owner(db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=branch_car.id, owner_id=repository.id)
    return repository


async def test_report_lists_repository_owners_links_with_owners_and_protected_values(
    db: InfrahubDatabase, repository: Node
) -> None:
    report = await build_ownership_report(db=db)

    assert report == OwnershipReport(
        repository_owners=[
            RepositoryOwnerRow(
                repository_id=repository.id,
                repository_kind="CoreRepository",
                node_kind="TestCar",
                attribute_name="color",
                branch="branch1",
                nb_attributes=1,
            ),
            RepositoryOwnerRow(
                repository_id=repository.id,
                repository_kind="CoreRepository",
                node_kind="TestCar",
                attribute_name="color",
                branch="main",
                nb_attributes=2,
            ),
        ],
        link_owners=[
            LinkOwnerRow(
                identifier="testcar__testperson",
                peer_kinds=("TestCar", "TestPerson"),
                owner_kind="CoreAccountGroup",
                branch="main",
                nb_links=1,
            ),
            LinkOwnerRow(
                identifier="testcar__testperson",
                peer_kinds=("TestCar", "TestPerson"),
                owner_kind="CoreRepository",
                branch="main",
                nb_links=1,
            ),
        ],
        protected_values=[
            ProtectedValueRow(node_kind="TestCar", attribute_name="color", branch="main", nb_values=1),
        ],
    )


async def test_report_of_a_database_without_any_case_is_empty(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> None:
    person = await _create(db=db, kind="TestPerson", name="John")
    await _create_car(db=db, name="plain-car", person=person)

    report = await build_ownership_report(db=db)

    assert report == OwnershipReport(repository_owners=[], link_owners=[], protected_values=[])


async def test_command_prints_each_section_with_its_rows(
    db: InfrahubDatabase, repository: Node, capsys: pytest.CaptureFixture[str]
) -> None:
    await ownership_report(db=db)

    assert capsys.readouterr().out.splitlines() == [
        "",
        "Attributes that a repository owns (the upgrade removes these owners): 2",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch branch1: 1",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch main: 2",
        "",
        "Relationships whose links have owners (the upgrade keeps these owners): 2",
        "  testcar__testperson (TestCar, TestPerson), owner kind CoreAccountGroup, branch main: 1",
        "  testcar__testperson (TestCar, TestPerson), owner kind CoreRepository, branch main: 1",
        "",
        "Attributes with values that have is_protected set (is_protected is deprecated): 1",
        "  TestCar.color, branch main: 1",
    ]
