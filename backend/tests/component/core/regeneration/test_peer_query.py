from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pytest

from infrahub.core import registry
from infrahub.core.node import Node
from infrahub.core.regeneration.peer_query import RelationshipPeerQuery
from tests.constants import TestKind
from tests.helpers.schema import CAR_SCHEMA, load_schema
from tests.helpers.test_app import TestInfrahubApp

if TYPE_CHECKING:
    from infrahub.core.branch import Branch
    from infrahub.database import InfrahubDatabase

RED = {"cars__color__value": "red"}


@dataclass(frozen=True, kw_only=True)
class PeerQueryCase:
    name: str
    owners: tuple[str, ...]
    peers: tuple[str, ...]
    filters: dict[str, Any] = field(default_factory=dict)
    expected: set[tuple[str, str]]


PEER_QUERY_CASES = [
    PeerQueryCase(
        name="a_filter_returns_only_the_peers_that_pass_it",
        owners=("maker-1",),
        peers=("red-1", "red-2", "blue-1"),
        filters=RED,
        expected={("maker-1", "red-1"), ("maker-1", "red-2")},
    ),
    PeerQueryCase(
        name="no_filter_returns_every_peer_of_the_owner",
        owners=("maker-1",),
        peers=("red-1", "blue-1"),
        expected={("maker-1", "red-1"), ("maker-1", "blue-1")},
    ),
    PeerQueryCase(
        name="only_the_given_peers_are_returned",
        owners=("maker-1",),
        peers=("blue-1",),
        filters=RED,
        expected=set(),
    ),
    PeerQueryCase(
        name="each_owner_returns_its_own_peers",
        owners=("maker-1", "maker-2"),
        peers=("red-1", "red-3"),
        filters=RED,
        expected={("maker-1", "red-1"), ("maker-2", "red-3")},
    ),
    PeerQueryCase(
        name="a_peer_of_another_owner_is_not_returned",
        owners=("maker-2",),
        peers=("red-1",),
        filters=RED,
        expected=set(),
    ),
    PeerQueryCase(
        name="a_read_selecting_peers_by_id_returns_only_the_selected_peers",
        owners=("maker-1",),
        peers=("red-1", "red-2"),
        filters={"cars__ids": ["red-1"]},
        expected={("maker-1", "red-1")},
    ),
    PeerQueryCase(name="no_owner_returns_nothing", owners=(), peers=("red-1",), filters=RED, expected=set()),
    PeerQueryCase(name="no_peer_returns_nothing", owners=("maker-1",), peers=(), filters=RED, expected=set()),
]


class TestRelationshipPeerQuery(TestInfrahubApp):
    """Two manufacturers: the first makes two red cars and a blue one, the second one red car."""

    @pytest.fixture(scope="class")
    async def ids(self, db: InfrahubDatabase, default_branch: Branch) -> dict[str, str]:
        await load_schema(db=db, schema=CAR_SCHEMA, update_db=True)
        owner = await Node.init(db=db, schema=TestKind.PERSON)
        await owner.new(db=db, name="owner")
        await owner.save(db=db)

        ids: dict[str, str] = {}
        for maker_name, cars in (("maker-1", ("red-1", "red-2", "blue-1")), ("maker-2", ("red-3",))):
            maker = await Node.init(db=db, schema=TestKind.MANUFACTURER)
            await maker.new(db=db, name=maker_name)
            await maker.save(db=db)
            ids[maker_name] = maker.id
            for car_name in cars:
                car = await Node.init(db=db, schema=TestKind.CAR)
                await car.new(db=db, name=car_name, color=car_name.split("-")[0], owner=owner, manufacturer=maker)
                await car.save(db=db)
                ids[car_name] = car.id
        return ids

    @pytest.mark.parametrize("case", PEER_QUERY_CASES, ids=lambda case: case.name)
    async def test_read(
        self, db: InfrahubDatabase, default_branch: Branch, ids: dict[str, str], case: PeerQueryCase
    ) -> None:
        query = RelationshipPeerQuery(
            db=db, branch=default_branch, schema_branch=registry.schema.get_schema_branch(name=default_branch.name)
        )
        filters = {
            key: [ids[name] for name in value] if key == "cars__ids" else value for key, value in case.filters.items()
        }

        pairs = await query.read(
            owner_kind=TestKind.MANUFACTURER,
            relationship_name="cars",
            owner_ids=[ids[name] for name in case.owners],
            peer_ids=[ids[name] for name in case.peers],
            filters=filters,
        )

        assert pairs == {(ids[owner], ids[peer]) for owner, peer in case.expected}
