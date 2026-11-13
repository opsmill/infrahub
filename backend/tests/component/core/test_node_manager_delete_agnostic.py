import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.database.validation import verify_graph
from infrahub.exceptions import ValidationError
from tests.helpers.node import create_chain, create_node
from tests.helpers.schema import load_schema
from tests.helpers.schema.agnostic_retirement import (
    AGNOSTIC_DELETE_SCHEMA,
    AGNOSTIC_GUARDIAN_SCHEMA,
    AGNOSTIC_ROSTER_SCHEMA,
    BADGE_KIND,
    CERTIFICATE_KIND,
    GUARDIAN_KIND,
    HOLDER_KIND,
    MEMBER_KIND,
    ROSTER_KIND,
    STICKER_KIND,
    TEAM_KIND,
)
from tests.helpers.schema.uplink import UPLINK_CORE_KIND, UPLINK_SCHEMA, UPLINK_SWITCH_KIND


@pytest.fixture
async def agnostic_delete_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    return registry.schema.register_schema(schema=AGNOSTIC_DELETE_SCHEMA, branch=default_branch.name)


@pytest.fixture
async def team(db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch) -> Node:
    return await create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")


@pytest.fixture
async def switch_chain(db: InfrahubDatabase, default_branch: Branch) -> tuple[Node, Node]:
    """Return a top switch and the leaf switch whose required upstream is the top switch, both on every branch."""
    registry.schema.register_schema(schema=UPLINK_SCHEMA, branch=default_branch.name)
    _, top, leaf = await create_chain(
        db=db,
        branch=default_branch,
        kinds=[UPLINK_CORE_KIND, UPLINK_SWITCH_KIND, UPLINK_SWITCH_KIND],
        relationship_name="upstream",
        name_prefix="switch",
    )
    await create_branch(db=db, branch_name="branch-holds-switches")
    return top, leaf


async def _move_member_to_team(db: InfrahubDatabase, branch: Branch, member: Node, team: Node) -> None:
    member_on_branch = await NodeManager.get_one(db=db, id=member.id, branch=branch, raise_on_error=True)
    await member_on_branch.team.update(db=db, data=team)  # type: ignore[attr-defined]
    await member_on_branch.save(db=db)


def _required_peer_message(team: Node, peer_kind: str, peer: Node, branch_names: str) -> str:
    return (
        f"Cannot delete {TEAM_KIND} '{team.id}'. It is linked to mandatory relationship team on node"
        f" {peer_kind} '{peer.id}' on {branch_names} at {peer_kind}.team"
    )


async def _count_edges_on_branch(db: InfrahubDatabase, branch_name: str) -> int:
    results = await db.execute_query(
        query="MATCH ()-[e]->() WHERE e.branch = $branch_name RETURN count(e) AS nbr_edges",
        params={"branch_name": branch_name},
    )
    return int(results[0]["nbr_edges"])


async def test_delete_refused_when_a_branch_holds_a_required_peer(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-holds-member")
    member = await create_node(db=db, branch=branch, kind=MEMBER_KIND, name="member-on-branch", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_keeps_a_cascade_target_with_an_optional_link_back_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-holds-badge")
    badge = await create_node(db=db, branch=branch, kind=BADGE_KIND, name="badge-on-branch", team=team)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None

    await verify_graph(db=db)


async def test_delete_keeps_a_cascade_target_that_does_not_declare_the_relationship_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-holds-sticker")
    sticker = await create_node(db=db, branch=branch, kind=STICKER_KIND, name="sticker-on-branch")
    team_on_branch = await NodeManager.get_one(db=db, id=team.id, branch=branch, raise_on_error=True)
    await team_on_branch.stickers.update(db=db, data=[sticker])  # type: ignore[attr-defined]
    await team_on_branch.save(db=db)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=sticker.id, branch=branch) is not None

    await verify_graph(db=db)


async def test_delete_refused_when_a_cascade_target_with_a_required_link_back_stays_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    certificate = await create_node(db=db, branch=default_branch, kind=CERTIFICATE_KIND, name="cert", team=team)
    branch = await create_branch(db=db, branch_name="branch-keeps-certificate")

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=CERTIFICATE_KIND, peer=certificate, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None
    assert await NodeManager.get_one(db=db, id=certificate.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_ignores_a_required_link_to_a_branch_aware_cascade_target_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    badge = await create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge", team=team)
    branch = await create_branch(db=db, branch_name="branch-holds-badge-holder")
    holder = await create_node(db=db, branch=branch, kind=HOLDER_KIND, name="holder-on-branch", badge=badge)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id, badge.id}
    assert await NodeManager.get_one(db=db, id=badge.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await NodeManager.get_one(db=db, id=holder.id, branch=branch) is not None

    await verify_graph(db=db)


async def test_delete_checks_a_branch_aware_node_deleted_with_a_branch_agnostic_one_on_the_request_branch_only(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    badge = await create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge")
    branch = await create_branch(db=db, branch_name="branch-holds-badge-holder")
    holder = await create_node(db=db, branch=branch, kind=HOLDER_KIND, name="holder-on-branch", badge=badge)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team, badge])

    assert {node.id for node in deleted} == {team.id, badge.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await NodeManager.get_one(db=db, id=holder.id, branch=branch) is not None

    await verify_graph(db=db)


async def test_delete_on_a_user_branch_refused_when_the_default_branch_holds_a_required_peer(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-requests-delete")
    member = await create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member-on-main", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{default_branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_refused_names_every_branch_that_inherits_a_required_link_in_one_error(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    other_team = await create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-2")
    member = await create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member", team=team)
    branches = [await create_branch(db=db, branch_name=name) for name in ("branch-b", "branch-a")]
    await _move_member_to_team(db=db, branch=default_branch, member=member, team=other_team)
    for branch in branches:
        assert await _count_edges_on_branch(db=db, branch_name=branch.name) == 0, (
            "precondition: the branch wrote nothing"
        )

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names="branches 'branch-a', 'branch-b'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_succeeds_and_cascades_only_on_the_request_branch(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    other_team = await create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-2")
    badge = await create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge", team=team)
    member = await create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member", team=team)
    await _move_member_to_team(db=db, branch=default_branch, member=member, team=other_team)
    branch = await create_branch(db=db, branch_name="branch-without-conflict")

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id, badge.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await _count_edges_on_branch(db=db, branch_name=branch.name) == 0

    await verify_graph(db=db)


async def test_delete_of_a_branch_aware_node_checks_only_the_request_branch(
    db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-holds-car")
    car = await create_node(
        db=db,
        branch=branch,
        kind="TestCar",
        name="car-on-branch",
        nbr_seats=4,
        is_electric=False,
        owner=person_jane_main,
    )

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[person_jane_main])

    assert {node.id for node in deleted} == {person_jane_main.id}
    assert await NodeManager.get_one(db=db, id=person_jane_main.id, branch=default_branch) is None
    car_on_branch = await NodeManager.get_one(db=db, id=car.id, branch=branch, raise_on_error=True)
    owner_on_branch = await car_on_branch.owner.get_peer(db=db)  # type: ignore[attr-defined]
    assert owner_on_branch is not None
    assert owner_on_branch.id == person_jane_main.id

    await verify_graph(db=db)


async def test_delete_refused_when_a_branch_aware_cascade_reaches_a_branch_agnostic_node_another_branch_requires(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_ROSTER_SCHEMA, branch=default_branch.name)
    roster = await create_node(db=db, branch=default_branch, kind=ROSTER_KIND, name="roster", teams=[team])
    branch = await create_branch(db=db, branch_name="branch-holds-member")
    member = await create_node(db=db, branch=branch, kind=MEMBER_KIND, name="member-on-branch", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[roster])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=roster.id, branch=default_branch) is not None
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_refused_when_a_relationship_required_only_in_another_branch_schema_holds_the_node(
    db: InfrahubDatabase, default_branch: Branch, team: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-adds-guardian")
    await load_schema(db=db, schema=AGNOSTIC_GUARDIAN_SCHEMA, branch_name=branch.name)
    guardian = await create_node(db=db, branch=branch, kind=GUARDIAN_KIND, name="guardian-on-branch", team=team)
    assert not registry.schema.get_schema_branch(name=default_branch.name).has(name=GUARDIAN_KIND), (
        "precondition: the default branch's schema does not define the requiring kind"
    )

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=GUARDIAN_KIND, peer=guardian, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None

    await verify_graph(db=db)


async def test_delete_ignores_a_peer_holding_the_node_through_the_optional_relationship_of_a_pair(
    db: InfrahubDatabase, default_branch: Branch, switch_chain: tuple[Node, Node]
) -> None:
    _, leaf = switch_chain

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[leaf])

    assert {node.id for node in deleted} == {leaf.id}

    await verify_graph(db=db)


async def test_delete_refused_names_the_required_relationship_of_a_pair(
    db: InfrahubDatabase, default_branch: Branch, switch_chain: tuple[Node, Node]
) -> None:
    top, leaf = switch_chain

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[top])

    assert str(exc.value) == (
        f"Cannot delete {UPLINK_SWITCH_KIND} '{top.id}'. It is linked to mandatory relationship upstream on node"
        f" {UPLINK_SWITCH_KIND} '{leaf.id}' on branches 'branch-holds-switches', '{default_branch.name}'"
        f" at {UPLINK_SWITCH_KIND}.upstream"
    )
    assert await NodeManager.get_one(db=db, id=top.id, branch=default_branch) is not None
    assert await NodeManager.get_one(db=db, id=leaf.id, branch=default_branch) is not None

    await verify_graph(db=db)
