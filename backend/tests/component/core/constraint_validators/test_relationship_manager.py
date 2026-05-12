import pytest

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.relationship.constraints.count import RelationshipCountConstraint
from infrahub.database import InfrahubDatabase
from infrahub.exceptions import ValidationError
from tests.helpers.schema.room import build_room_schema


async def _make_person(db: InfrahubDatabase, branch: Branch, name: str, room_ids: list[str]) -> Node:
    person = await Node.init(db=db, schema="TestPerson", branch=branch)
    await person.new(db=db, name=name, rooms=room_ids)
    return person


async def _make_room(db: InfrahubDatabase, branch: Branch, kind: str, name: str) -> Node:
    room = await Node.init(db=db, schema=kind, branch=branch)
    await room.new(db=db, name=name)
    await room.save(db=db)
    return room


async def test_node_validate_constraint_relationship_count_failure(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)
    person = await Node.init(db=db, schema="TestPerson", branch=default_branch)
    await person.new(db=db, name="Alfred", height=160, cars=[car_accord_main.id])

    with pytest.raises(ValidationError) as exc:
        await constraint.check(relm=person.cars, node_schema=person.get_schema(), node=person)

    assert "has 2 peers for testcar__testperson, maximum of 1 allowed" in exc.value.message


async def test_node_validate_constraint_relationship_count_success(
    db: InfrahubDatabase, default_branch: Branch, car_accord_main: Node, car_volt_main: Node, person_john_main: Node
) -> None:
    constraint = RelationshipCountConstraint(db=db, branch=default_branch)

    await constraint.check(relm=person_john_main.cars, node_schema=person_john_main.get_schema(), node=person_john_main)


class TestCountGenericPeerCardinalityOne:
    """Cardinality=one declared only on a concrete subtype while the relationship's
    declared peer is the parent generic."""

    @pytest.fixture(autouse=True)
    async def _register(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=build_room_schema(), branch=default_branch.name)

    async def test_failure_when_concrete_peer_at_limit(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

        assert "has 2 peers for person__room, maximum of 1 allowed" in exc.value.message

    async def test_success_when_concrete_peer_has_no_owner(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=alice.rooms, node_schema=alice.get_schema(), node=alice)

    async def test_success_when_resaving_same_peer(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)

        # Re-load alice so the RelationshipManager observes the post-save state,
        # then re-assert the same peer. The constraint must treat this as a no-op.
        alice = await NodeManager.get_one(db=db, id=alice.id, branch=default_branch)
        await alice.rooms.get_relationships(db=db)
        await alice.rooms.update(db=db, data=[single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=alice.rooms, node_schema=alice.get_schema(), node=alice)


class TestCountGenericPeerWithGenericRel:
    """Cardinality=one declared on the generic itself."""

    @pytest.fixture(autouse=True)
    async def _register(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=build_room_schema(generic_has_rel=True), branch=default_branch.name)

    async def test_failure_when_peer_at_limit(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

        assert "has 2 peers for person__room, maximum of 1 allowed" in exc.value.message

    async def test_success_when_under_limit(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=alice.rooms, node_schema=alice.get_schema(), node=alice)


class TestCountGenericPeerMixedSubtypes:
    """Generic with two concrete subtypes that declare different cardinalities for
    the same identifier."""

    @pytest.fixture(autouse=True)
    async def _register(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(schema=build_room_schema(include_dorm_subtype=True), branch=default_branch.name)

    async def test_failure_when_exclusive_subtype_over_limit(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

        assert "has 2 peers for person__room, maximum of 1 allowed" in exc.value.message

    async def test_success_when_shared_subtype_over_limit(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        dorm = await _make_room(db, default_branch, "TestDorm", "dorm")
        alice = await _make_person(db, default_branch, "alice", [dorm.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [dorm.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

    async def test_failure_when_mixed_peers_only_exclusive_violates(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        dorm = await _make_room(db, default_branch, "TestDorm", "dorm")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id, dorm.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

        assert single.id in exc.value.message
        assert "maximum of 1 allowed" in exc.value.message


class TestCountGenericPeerMaxCount:
    """max_count > 1 declared on a concrete subtype only."""

    @pytest.fixture(autouse=True)
    async def _register(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(
            schema=build_room_schema(single_room_cardinality="many", single_room_max_count=3),
            branch=default_branch.name,
        )

    async def test_failure_when_max_count_exceeded(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        for name in ("p1", "p2", "p3"):
            person = await _make_person(db, default_branch, name, [single.id])
            await person.save(db=db)
        extra = await _make_person(db, default_branch, "extra", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=extra.rooms, node_schema=extra.get_schema(), node=extra)

        assert "maximum of 3 allowed" in exc.value.message

    async def test_success_when_max_count_not_reached(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        for name in ("p1", "p2"):
            person = await _make_person(db, default_branch, name, [single.id])
            await person.save(db=db)
        extra = await _make_person(db, default_branch, "extra", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=extra.rooms, node_schema=extra.get_schema(), node=extra)


class TestCountGenericPeerMinCount:
    """min_count declared on a concrete subtype only."""

    @pytest.fixture(autouse=True)
    async def _register(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        registry.schema.register_schema(
            schema=build_room_schema(single_room_cardinality="many", single_room_min_count=1),
            branch=default_branch.name,
        )

    async def test_failure_when_removing_drops_below_min(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)

        # Re-load alice so the RelationshipManager observes the post-save state.
        alice = await NodeManager.get_one(db=db, id=alice.id, branch=default_branch)
        await alice.rooms.get_relationships(db=db)
        await alice.rooms.update(db=db, data=[])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=alice.rooms, node_schema=alice.get_schema(), node=alice)

        assert "no fewer than 1 allowed" in exc.value.message

    async def test_success_when_removing_stays_above_min(self, db: InfrahubDatabase, default_branch: Branch) -> None:
        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id])
        await bob.save(db=db)

        alice = await NodeManager.get_one(db=db, id=alice.id, branch=default_branch)
        await alice.rooms.get_relationships(db=db)
        await alice.rooms.update(db=db, data=[])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        await constraint.check(relm=alice.rooms, node_schema=alice.get_schema(), node=alice)


class TestCountGenericPeerDirection:
    """Direction variations on a generic-peer relationship."""

    async def test_failure_when_bidirectional_concrete_at_limit(
        self, db: InfrahubDatabase, default_branch: Branch
    ) -> None:
        registry.schema.register_schema(
            schema=build_room_schema(
                single_room_direction="bidirectional",
                person_direction="bidirectional",
            ),
            branch=default_branch.name,
        )

        single = await _make_room(db, default_branch, "TestSingleRoom", "single")
        alice = await _make_person(db, default_branch, "alice", [single.id])
        await alice.save(db=db)
        bob = await _make_person(db, default_branch, "bob", [single.id])

        constraint = RelationshipCountConstraint(db=db, branch=default_branch)
        with pytest.raises(ValidationError) as exc:
            await constraint.check(relm=bob.rooms, node_schema=bob.get_schema(), node=bob)

        assert "maximum of 1 allowed" in exc.value.message
