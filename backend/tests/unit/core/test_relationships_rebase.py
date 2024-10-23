from random import choice
from typing import Any, NamedTuple

import pytest

from infrahub.core.branch import Branch
from infrahub.core.initialization import create_branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.timestamp import Timestamp
from infrahub.database import InfrahubDatabase


class DatabaseEdge(NamedTuple):
    type: str
    branch: str
    status: str
    from_time: Timestamp
    to_time: Timestamp | None


class DatabasePath(NamedTuple):
    uuid: str
    peer_or_value: Any
    edge_1: DatabaseEdge
    edge_2: DatabaseEdge


async def get_database_edges_state(
    db: InfrahubDatabase,
    node_uuids: list[str],
    rel_identiers: list[str],
) -> set[DatabasePath]:
    query = """
        MATCH (n:Node)-[r1:IS_RELATED]-(r:Relationship)-[r2]-(peer)
        WHERE n.uuid in $node_uuids
        AND r.name in $rel_identifiers
        AND r1.branch = r2.branch
        RETURN n, r1, r2, peer
        """
    results = await db.execute_query(query=query, params={"node_uuids": node_uuids, "rel_identifiers": rel_identiers})
    retrieved_path_tuples = set()
    for result in results:
        node_uuid = result.get("n").get("uuid")
        r1 = result.get("r1")
        r2 = result.get("r2")
        edges_tuples = []
        for edge in [r1, r2]:
            to_time_str = r1.get("to")
            to_time = Timestamp(to_time_str) if to_time_str else None
            edges_tuples.append(
                DatabaseEdge(
                    type=edge.type,
                    branch=edge.get("branch"),
                    status=edge.get("status"),
                    from_time=Timestamp(edge.get("from")),
                    to_time=to_time,
                )
            )
        peer = result.get("peer")
        peer_id_or_value = peer.get("uuid", peer.get("value"))
        retrieved_path_tuples.add(
            DatabasePath(uuid=node_uuid, edge_1=edges_tuples[0], edge_2=edges_tuples[1], peer_or_value=peer_id_or_value)
        )
    return retrieved_path_tuples


class TestRelationshipsWithRebase:
    async def verify_database_state_cardinality_one(
        self,
        db: InfrahubDatabase,
        car_uuid: str,
        main_peer_id: str,
        branch_peer_id: str,
        branch_name: str,
        rebase_time: Timestamp,
    ):
        database_paths = await get_database_edges_state(
            db=db, node_uuids=[car_uuid], rel_identiers=["testcar__testperson"]
        )
        # node_uuid, (type, branch, status, from_time == rebased_time, to_time == rebased_time) * 2, uuid OR value
        retrieved_path_tuples = {
            (
                db_path.uuid,
                (
                    db_path.edge_1.type,
                    db_path.edge_1.branch,
                    db_path.edge_1.status,
                    db_path.edge_1.from_time == rebase_time,
                    db_path.edge_1.to_time == rebase_time,
                ),
                (
                    db_path.edge_2.type,
                    db_path.edge_2.branch,
                    db_path.edge_2.status,
                    db_path.edge_2.from_time == rebase_time,
                    db_path.edge_2.to_time == rebase_time,
                ),
                db_path.peer_or_value,
            )
            for db_path in database_paths
        }

        expected_path_tuples = {
            (
                car_uuid,
                ("IS_RELATED", "main", "active", False, False),
                ("IS_RELATED", "main", "active", False, False),
                main_peer_id,
            ),
            (
                car_uuid,
                ("IS_RELATED", "main", "active", False, False),
                ("IS_VISIBLE", "main", "active", False, False),
                True,
            ),
            (
                car_uuid,
                ("IS_RELATED", "main", "active", False, False),
                ("IS_PROTECTED", "main", "active", False, False),
                False,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "deleted", True, False),
                ("IS_RELATED", branch_name, "deleted", True, False),
                main_peer_id,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "deleted", True, False),
                ("IS_VISIBLE", branch_name, "deleted", True, False),
                True,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "deleted", True, False),
                ("IS_PROTECTED", branch_name, "deleted", True, False),
                False,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "active", True, False),
                ("IS_RELATED", branch_name, "active", True, False),
                branch_peer_id,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "active", True, False),
                ("IS_VISIBLE", branch_name, "active", True, False),
                True,
            ),
            (
                car_uuid,
                ("IS_RELATED", branch_name, "active", True, False),
                ("IS_PROTECTED", branch_name, "active", True, False),
                False,
            ),
        }

        assert expected_path_tuples == retrieved_path_tuples

    @pytest.mark.parametrize("num_updates", [2, 3])
    async def test_rebase_cardinality_one(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
        person_john_main: Node,
        person_alfred_main: Node,
        person_jane_main: Node,
        person_jim_main: Node,
        car_accord_main: Node,
        num_updates: int,
    ):
        branch_2 = await create_branch(db=db, branch_name="branch_2")
        car_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch_2)
        await car_branch.owner.update(db=db, data=person_alfred_main)
        await car_branch.save(db=db)
        if num_updates > 2:
            car_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch_2)
            await car_branch.owner.update(db=db, data=person_jim_main)
            await car_branch.save(db=db)
        car_branch = await NodeManager.get_one(db=db, id=car_accord_main.id, branch=branch_2)
        await car_branch.owner.update(db=db, data=person_jane_main)
        await car_branch.save(db=db)

        rebase_time = Timestamp()
        await branch_2.rebase(db=db, at=rebase_time)

        rebased_car = await NodeManager.get_one(db=db, branch=branch_2, id=car_branch.id)
        owner_peer = await rebased_car.owner.get_peer(db=db)
        assert owner_peer.id == person_jane_main.id
        main_car = await NodeManager.get_one(db=db, id=car_branch.id)
        owner_peer = await main_car.owner.get_peer(db=db)
        assert owner_peer.id == person_john_main.id
        await self.verify_database_state_cardinality_one(
            db=db,
            car_uuid=car_accord_main.id,
            main_peer_id=person_john_main.id,
            branch_peer_id=person_jane_main.id,
            branch_name=branch_2.name,
            rebase_time=rebase_time,
        )

    async def verify_database_state_cardinality_many(
        self,
        db: InfrahubDatabase,
        person_uuids: list[str],
        car_person_id_map_main: dict[str, str],
        car_person_id_map_branch: dict[str, str],
        branch_name: str,
        rebase_time: Timestamp,
    ):
        database_paths = await get_database_edges_state(
            db=db, node_uuids=person_uuids, rel_identiers=["testcar__testperson"]
        )
        retrieved_path_tuples = {
            (
                db_path.uuid,
                (
                    db_path.edge_1.type,
                    db_path.edge_1.branch,
                    db_path.edge_1.status,
                    db_path.edge_1.from_time == rebase_time,
                    db_path.edge_1.to_time == rebase_time,
                ),
                (
                    db_path.edge_2.type,
                    db_path.edge_2.branch,
                    db_path.edge_2.status,
                    db_path.edge_2.from_time == rebase_time,
                    db_path.edge_2.to_time == rebase_time,
                ),
                db_path.peer_or_value,
            )
            for db_path in database_paths
        }

        expected_path_tuples = set()
        for person_uuid in person_uuids:
            expected_car_ids_main = {c_id for c_id, p_id in car_person_id_map_main.items() if p_id == person_uuid}
            for car_id in expected_car_ids_main:
                expected_path_tuples.update((
                            person_uuid,
                            ("IS_RELATED", "main", "active", False, False),
                            (edge_type, "main", "active", False, False),
                            peer_or_value,
                        ) for edge_type, peer_or_value in (("IS_RELATED", car_id), ("IS_VISIBLE", True), ("IS_PROTECTED", False)))
                expected_path_tuples.update((
                            person_uuid,
                            ("IS_RELATED", branch_name, "deleted", True, False),
                            (edge_type, branch_name, "deleted", True, False),
                            peer_or_value,
                        ) for edge_type, peer_or_value in (("IS_RELATED", car_id), ("IS_VISIBLE", True), ("IS_PROTECTED", False)))

            expected_car_ids_branch = {c_id for c_id, p_id in car_person_id_map_branch.items() if p_id == person_uuid}
            for car_id in expected_car_ids_branch:
                expected_path_tuples.update((
                            person_uuid,
                            ("IS_RELATED", branch_name, "active", True, False),
                            (edge_type, branch_name, "active", True, False),
                            peer_or_value,
                        ) for edge_type, peer_or_value in (("IS_RELATED", car_id), ("IS_VISIBLE", True), ("IS_PROTECTED", False)))

        for ept in expected_path_tuples:
            assert ept in retrieved_path_tuples

        assert expected_path_tuples == retrieved_path_tuples

    async def test_rebase_cardinality_many(
        self,
        db: InfrahubDatabase,
        default_branch: Branch,
        car_person_schema: SchemaBranch,
    ):
        people = []
        cars = []
        car_person_id_map_main = {}
        for i in range(3):
            person = await Node.init(db=db, schema="TestPerson")
            await person.new(db=db, name=f"Person{i}")
            await person.save(db=db)
            people.append(person)
            for j in range(2):
                car = await Node.init(db=db, schema="TestCar")
                await car.new(db=db, name=f"Car{i}{j}", owner=person)
                await car.save(db=db)
                cars.append(car)
                car_person_id_map_main[car.id] = person.id
        branch_2 = await create_branch(db=db, branch_name="branch_2")
        # make a bunch of branch updates
        car_person_id_map_branch = {}
        for _ in range(3):
            for car in cars:
                branch_car = await NodeManager.get_one(db=db, branch=branch_2, id=car.id)
                owner_peer = await branch_car.owner.get_peer(db=db)
                random_person = choice([p for p in people if p.id != owner_peer.id])
                await branch_car.owner.update(db=db, data=random_person)
                await branch_car.save(db=db)
                car_person_id_map_branch[car.id] = random_person.id

        rebase_time = Timestamp()
        await branch_2.rebase(db=db, at=rebase_time)

        for person in people:
            main_person = await NodeManager.get_one(db=db, branch=default_branch, id=person.id)
            expected_car_ids = {c_id for c_id, p_id in car_person_id_map_main.items() if p_id == person.id}
            car_peers = await main_person.cars.get_peers(db=db)
            retrieved_car_ids = set(car_peers.keys())
            assert expected_car_ids == retrieved_car_ids
        for car in cars:
            main_car = await NodeManager.get_one(db=db, branch=default_branch, id=car.id)
            owner_peer = await main_car.owner.get_peer(db=db)
            assert owner_peer.id == car_person_id_map_main[car.id]

        for person in people:
            rebased_person = await NodeManager.get_one(db=db, branch=branch_2, id=person.id)
            expected_car_ids = {c_id for c_id, p_id in car_person_id_map_branch.items() if p_id == person.id}
            car_peers = await rebased_person.cars.get_peers(db=db)
            retrieved_car_ids = set(car_peers.keys())
            assert expected_car_ids == retrieved_car_ids
        for car in cars:
            rebased_car = await NodeManager.get_one(db=db, branch=branch_2, id=car.id)
            owner_peer = await rebased_car.owner.get_peer(db=db)
            assert owner_peer.id == car_person_id_map_branch[car.id]
        await self.verify_database_state_cardinality_many(
            db=db,
            person_uuids=[p.id for p in people],
            car_person_id_map_main=car_person_id_map_main,
            car_person_id_map_branch=car_person_id_map_branch,
            branch_name=branch_2.name,
            rebase_time=rebase_time,
        )
