from typing import Any

import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
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


@pytest.fixture
async def agnostic_delete_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    return registry.schema.register_schema(schema=AGNOSTIC_DELETE_SCHEMA, branch=default_branch.name)


async def _create_node(db: InfrahubDatabase, branch: Branch, kind: str, **data: Any) -> Node:
    node = await Node.init(db=db, schema=kind, branch=branch)
    await node.new(db=db, **data)
    await node.save(db=db)
    return node


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
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    branch = await create_branch(db=db, branch_name="branch-holds-member")
    member = await _create_node(db=db, branch=branch, kind=MEMBER_KIND, name="member-on-branch", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None


async def test_delete_refused_when_a_branch_inherits_the_required_link_from_before_it_was_created(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team_1 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    team_2 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-2")
    member = await _create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member", team=team_1)
    branch = await create_branch(db=db, branch_name="branch-inherits-link")
    await _move_member_to_team(db=db, branch=default_branch, member=member, team=team_2)
    assert await _count_edges_on_branch(db=db, branch_name=branch.name) == 0, "precondition: the branch wrote nothing"

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team_1])

    message = str(exc.value)
    assert f"Cannot delete {TEAM_KIND} '{team_1.id}'" in message
    assert f"{MEMBER_KIND} '{member.id}'" in message
    assert f"'{branch.name}'" in message
    assert await NodeManager.get_one(db=db, id=team_1.id, branch=default_branch) is not None


async def test_delete_keeps_a_cascade_target_with_an_optional_link_back_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    branch = await create_branch(db=db, branch_name="branch-holds-badge")
    badge = await _create_node(db=db, branch=branch, kind=BADGE_KIND, name="badge-on-branch", team=team)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None


async def test_delete_keeps_a_cascade_target_that_does_not_declare_the_relationship_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    branch = await create_branch(db=db, branch_name="branch-holds-sticker")
    sticker = await _create_node(db=db, branch=branch, kind=STICKER_KIND, name="sticker-on-branch")
    team_on_branch = await NodeManager.get_one(db=db, id=team.id, branch=branch, raise_on_error=True)
    await team_on_branch.stickers.update(db=db, data=[sticker])  # type: ignore[attr-defined]
    await team_on_branch.save(db=db)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=sticker.id, branch=branch) is not None


async def test_delete_refused_when_a_cascade_target_with_a_required_link_back_stays_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    certificate = await _create_node(db=db, branch=default_branch, kind=CERTIFICATE_KIND, name="cert", team=team)
    branch = await create_branch(db=db, branch_name="branch-keeps-certificate")

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=CERTIFICATE_KIND, peer=certificate, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None
    assert await NodeManager.get_one(db=db, id=certificate.id, branch=default_branch) is not None


async def test_delete_ignores_a_required_link_to_a_branch_aware_cascade_target_on_another_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    badge = await _create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge", team=team)
    branch = await create_branch(db=db, branch_name="branch-holds-badge-holder")
    holder = await _create_node(db=db, branch=branch, kind=HOLDER_KIND, name="holder-on-branch", badge=badge)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert {node.id for node in deleted} == {team.id, badge.id}
    assert await NodeManager.get_one(db=db, id=badge.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await NodeManager.get_one(db=db, id=holder.id, branch=branch) is not None


async def test_delete_checks_a_branch_aware_node_deleted_with_a_branch_agnostic_one_on_the_request_branch_only(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    badge = await _create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge")
    branch = await create_branch(db=db, branch_name="branch-holds-badge-holder")
    holder = await _create_node(db=db, branch=branch, kind=HOLDER_KIND, name="holder-on-branch", badge=badge)

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team, badge])

    assert {node.id for node in deleted} == {team.id, badge.id}
    assert await NodeManager.get_one(db=db, id=team.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await NodeManager.get_one(db=db, id=holder.id, branch=branch) is not None


async def test_delete_on_a_user_branch_refused_when_the_default_branch_holds_a_required_peer(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    branch = await create_branch(db=db, branch_name="branch-requests-delete")
    member = await _create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member-on-main", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{default_branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None


async def test_delete_refused_names_every_blocking_branch_in_one_error(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team_1 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    team_2 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-2")
    member = await _create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member", team=team_1)
    await create_branch(db=db, branch_name="branch-b")
    await create_branch(db=db, branch_name="branch-a")
    await _move_member_to_team(db=db, branch=default_branch, member=member, team=team_2)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team_1])

    assert str(exc.value) == _required_peer_message(
        team=team_1, peer_kind=MEMBER_KIND, peer=member, branch_names="branches 'branch-a', 'branch-b'"
    )


async def test_delete_succeeds_and_cascades_only_on_the_request_branch(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team_1 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    team_2 = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-2")
    badge = await _create_node(db=db, branch=default_branch, kind=BADGE_KIND, name="badge", team=team_1)
    member = await _create_node(db=db, branch=default_branch, kind=MEMBER_KIND, name="member", team=team_1)
    await _move_member_to_team(db=db, branch=default_branch, member=member, team=team_2)
    branch = await create_branch(db=db, branch_name="branch-without-conflict")

    deleted = await NodeManager.delete(db=db, branch=default_branch, nodes=[team_1])

    assert {node.id for node in deleted} == {team_1.id, badge.id}
    assert await NodeManager.get_one(db=db, id=team_1.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=team_1.id, branch=branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=default_branch) is None
    assert await NodeManager.get_one(db=db, id=badge.id, branch=branch) is not None
    assert await _count_edges_on_branch(db=db, branch_name=branch.name) == 0


async def test_delete_of_a_branch_aware_node_checks_only_the_request_branch(
    db: InfrahubDatabase, default_branch: Branch, person_jane_main: Node
) -> None:
    branch = await create_branch(db=db, branch_name="branch-holds-car")
    car = await _create_node(
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


async def test_delete_refused_when_a_branch_aware_cascade_reaches_a_branch_agnostic_node_another_branch_requires(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    registry.schema.register_schema(schema=AGNOSTIC_ROSTER_SCHEMA, branch=default_branch.name)
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    roster = await _create_node(db=db, branch=default_branch, kind=ROSTER_KIND, name="roster", teams=[team])
    branch = await create_branch(db=db, branch_name="branch-holds-member")
    member = await _create_node(db=db, branch=branch, kind=MEMBER_KIND, name="member-on-branch", team=team)

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[roster])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=MEMBER_KIND, peer=member, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=roster.id, branch=default_branch) is not None
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None


async def test_delete_refused_when_a_relationship_required_only_in_another_branch_schema_holds_the_node(
    db: InfrahubDatabase, default_branch: Branch, agnostic_delete_schema: SchemaBranch
) -> None:
    team = await _create_node(db=db, branch=default_branch, kind=TEAM_KIND, name="team-1")
    branch = await create_branch(db=db, branch_name="branch-adds-guardian")
    await load_schema(db=db, schema=AGNOSTIC_GUARDIAN_SCHEMA, branch_name=branch.name)
    guardian = await _create_node(db=db, branch=branch, kind=GUARDIAN_KIND, name="guardian-on-branch", team=team)
    assert not registry.schema.get_schema_branch(name=default_branch.name).has(name=GUARDIAN_KIND), (
        "precondition: the default branch's schema does not define the requiring kind"
    )

    with pytest.raises(ValidationError) as exc:
        await NodeManager.delete(db=db, branch=default_branch, nodes=[team])

    assert str(exc.value) == _required_peer_message(
        team=team, peer_kind=GUARDIAN_KIND, peer=guardian, branch_names=f"branch '{branch.name}'"
    )
    assert await NodeManager.get_one(db=db, id=team.id, branch=default_branch) is not None
