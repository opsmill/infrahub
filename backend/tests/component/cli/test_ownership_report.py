import pytest

from infrahub.cli.db_commands.ownership_report import ownership_report
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_branch, get_root_node
from infrahub.core.migrations.graph.m085_close_repository_owner_edges import Migration085
from infrahub.core.migrations.query.node_duplicate import NodeDuplicateQuery, SchemaNodeInfo
from infrahub.core.node import Node
from infrahub.core.ownership.report import (
    OwnershipReport,
    ProtectedValueRow,
    RepositoryOwnerRow,
    build_ownership_report,
)
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase
from tests.helpers.ownership import ADD_ATTRIBUTE_OWNER, ADD_LINK_OWNER, add_node, add_owner_edge


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


async def _set_graph_version(db: InfrahubDatabase, graph_version: int) -> None:
    root = await get_root_node(db=db)
    root.graph_version = graph_version
    await root.save(db=db)


@pytest.fixture
async def repository(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> Node:
    """Create each case of the report, and the cases that the report leaves out.

    The repository owns the color of two cars on the default branch and of one car on a branch, and one link.
    An account group owns one color and one link. A person owns one color. One color is protected. One car has no
    owner and no protection. The report leaves out a closed repository owner edge and a deleted one.
    """
    repository = await add_node(
        db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git"
    )
    group = await add_node(db=db, kind=InfrahubKind.ACCOUNTGROUP, name="network-team")
    person = await add_node(db=db, kind="TestPerson", name="John")

    for name in ("repository-car-1", "repository-car-2"):
        car = await _create_car(db=db, name=name, person=person)
        await add_owner_edge(
            db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
        )
    await add_owner_edge(db=db, query=ADD_LINK_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id)
    await _create_car(db=db, name="group-car", person=person, color_owner_id=group.id, link_owner_id=group.id)
    person_car = await _create_car(db=db, name="person-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=person_car.id, owner_id=person.id
    )
    await _create_car(db=db, name="protected-car", person=person, is_protected=True)
    branch_car = await _create_car(db=db, name="plain-car", person=person)
    branch = await create_branch(db=db, branch_name="branch1")
    await add_owner_edge(db=db, query=ADD_ATTRIBUTE_OWNER, branch=branch, node_id=branch_car.id, owner_id=repository.id)
    closed_car = await _create_car(db=db, name="closed-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=closed_car.id, owner_id=repository.id
    )
    await db.execute_query(
        query="""
MATCH (:Node {uuid: $node_id})-[:HAS_ATTRIBUTE]->(:Attribute {name: "color"})-[r:HAS_OWNER]->()
SET r.to = $at
        """,
        params={"node_id": closed_car.id, "at": Timestamp().to_string()},
    )
    await db.execute_query(
        query=ADD_ATTRIBUTE_OWNER.replace('status: "active"', 'status: "deleted"'),
        params={
            "node_id": closed_car.id,
            "owner_id": repository.id,
            "branch": branch.name,
            "branch_level": branch.hierarchy_level,
            "at": Timestamp().to_string(),
        },
    )
    return repository


async def test_report_of_a_database_without_any_case_is_empty(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> None:
    person = await add_node(db=db, kind="TestPerson", name="John")
    await _create_car(db=db, name="plain-car", person=person)

    report = await build_ownership_report(db=db)

    assert report == OwnershipReport(repository_owners=[], other_owners=[], link_owners=[], protected_values=[])


async def test_command_prints_each_section_with_its_rows(
    db: InfrahubDatabase, repository: Node, capsys: pytest.CaptureFixture[str]
) -> None:
    await _set_graph_version(db=db, graph_version=Migration085.init().minimum_version)

    await ownership_report(db=db)

    assert capsys.readouterr().out.splitlines() == [
        "",
        "Attributes that a repository owns (the upgrade removes these owners): 3",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch branch1: 1",
        f"  TestCar.color, repository {repository.id} (CoreRepository), branch main: 2",
        "",
        "Attributes that a node other than an account, an account group or a repository owns"
        " (the upgrade keeps these owners): 1",
        "  TestPerson owns TestCar.color, branch main: 1",
        "",
        "Relationships whose links have owners (the upgrade keeps these owners): 1",
        "  testcar__testperson (TestCar, TestPerson), owner kind CoreAccountGroup, branch main: 1",
        "  testcar__testperson (TestCar, TestPerson), owner kind CoreRepository, branch main: 1",
        "",
        "Attributes with values that have is_protected set (is_protected is deprecated): 1",
        "  TestCar.color, branch main: 1",
    ]


async def test_command_after_the_upgrade_warns_that_the_first_section_is_empty(
    db: InfrahubDatabase,
    default_branch: Branch,
    register_core_models_schema: SchemaBranch,
    car_person_schema: None,
    capsys: pytest.CaptureFixture[str],
) -> None:
    await _set_graph_version(db=db, graph_version=Migration085.init().number)

    await ownership_report(db=db)

    assert capsys.readouterr().out.splitlines() == [
        "The upgrade already ran on this database. It closed the owner edges from attributes to repositories, so the"
        " first section lists none of them.",
        "",
        "Attributes that a repository owns (the upgrade removes these owners): 0",
        "",
        "Attributes that a node other than an account, an account group or a repository owns"
        " (the upgrade keeps these owners): 0",
        "",
        "Relationships whose links have owners (the upgrade keeps these owners): 0",
        "",
        "Attributes with values that have is_protected set (is_protected is deprecated): 0",
    ]


async def test_report_skips_a_deleted_node(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> None:
    repository = await add_node(
        db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git"
    )
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await _create_car(db=db, name="deleted-car", person=person, is_protected=True)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
    )

    await car.delete(db=db)

    report = await build_ownership_report(db=db)
    assert report == OwnershipReport(repository_owners=[], other_owners=[], link_owners=[], protected_values=[])


async def test_report_skips_the_vertex_that_a_kind_migration_replaced(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> None:
    repository = await add_node(
        db=db, kind=InfrahubKind.REPOSITORY, name="repo01", location="git@github.com:user/repo01.git"
    )
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await _create_car(db=db, name="migrated-car", person=person, is_protected=True)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
    )
    # The migration gives the attributes to a new vertex of the new kind, and closes the edges of the old vertex.
    migration = await NodeDuplicateQuery.init(
        db=db,
        branch=default_branch,
        kind_updates_map={
            "TestCar": SchemaNodeInfo(name="Vehicle", namespace="Test", labels=["TestVehicle"], kind="TestVehicle")
        },
    )
    await migration.execute(db=db)

    report = await build_ownership_report(db=db)

    assert report == OwnershipReport(
        repository_owners=[
            RepositoryOwnerRow(
                repository_id=repository.id,
                repository_kind=InfrahubKind.REPOSITORY,
                node_kind="TestVehicle",
                attribute_name="color",
                branch=default_branch.name,
                nb_attributes=1,
            )
        ],
        other_owners=[],
        link_owners=[],
        protected_values=[
            ProtectedValueRow(node_kind="TestVehicle", attribute_name="color", branch=default_branch.name, nb_values=1)
        ],
    )


async def test_report_lists_a_read_only_repository_as_owner(
    db: InfrahubDatabase, default_branch: Branch, register_core_models_schema: SchemaBranch, car_person_schema: None
) -> None:
    repository = await add_node(
        db=db,
        kind=InfrahubKind.READONLYREPOSITORY,
        name="repo02",
        location="git@github.com:user/repo02.git",
        ref="main",
    )
    person = await add_node(db=db, kind="TestPerson", name="John")
    car = await _create_car(db=db, name="read-only-car", person=person)
    await add_owner_edge(
        db=db, query=ADD_ATTRIBUTE_OWNER, branch=default_branch, node_id=car.id, owner_id=repository.id
    )

    report = await build_ownership_report(db=db)

    assert report.repository_owners == [
        RepositoryOwnerRow(
            repository_id=repository.id,
            repository_kind=InfrahubKind.READONLYREPOSITORY,
            node_kind="TestCar",
            attribute_name="color",
            branch=default_branch.name,
            nb_attributes=1,
        )
    ]
