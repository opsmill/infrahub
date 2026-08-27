"""Cost of the primary-node HFID read: materialized (in-memory) vs computed (hits the DB).

get_hfid reads the materialized human_friendly_id value in memory when it is present, and
otherwise recomputes it -- resolving a relationship peer from the database for every
relationship-based component of the HFID. This measures both paths, with a query counter, on a
node whose HFID depends on a relationship (owner__name__value + name__value).
"""

from typing import AsyncGenerator
import time

from infrahub.core.branch import Branch
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.database import InfrahubDatabase

from tests.helpers.db_query_counter import CountingInfrahubDatabase

_ITERS = 20


async def test_hfid_materialized_vs_computed_db_cost(
    db: AsyncGenerator[InfrahubDatabase, None],
    default_branch: Branch,
    animal_person_schema: SchemaBranch,
) -> None:
    person = await Node.init(db=db, schema=animal_person_schema.get(name="TestPerson"), branch=default_branch)
    await person.new(db=db, name={"value": "Jack"})
    await person.save(db=db)
    dog = await Node.init(db=db, schema=animal_person_schema.get(name="TestDog"), branch=default_branch)
    await dog.new(db=db, name={"value": "Rocky"}, breed="Labrador", owner=person)
    await dog.save(db=db)

    counting = CountingInfrahubDatabase.from_db(db)

    # Materialized path: value already on the node -> in-memory read, no query.
    materialized = await NodeManager.get_one(db=counting, id=dog.id, branch=default_branch)
    counting.query_counts.clear()
    t0 = time.perf_counter()
    for _ in range(_ITERS):
        hfid_mat = await materialized.get_hfid(db=counting)
    mat_ms = (time.perf_counter() - t0) * 1000 / _ITERS
    mat_queries = sum(counting.query_counts.values())

    # Computed path: drop the materialized value so get_hfid recomputes each component;
    # owner__name__value forces a peer resolve from the DB. The re-fetch that resets the
    # resolved state is done OUTSIDE the counted/timed window so only get_hfid is measured.
    comp_queries = 0
    comp_ms = 0.0
    hfid_comp: list[str] | None = None
    for _ in range(_ITERS):
        fresh = await NodeManager.get_one(db=counting, id=dog.id, branch=default_branch)
        fresh._human_friendly_id = None
        counting.query_counts.clear()
        t0 = time.perf_counter()
        hfid_comp = await fresh.get_hfid(db=counting)
        comp_ms += (time.perf_counter() - t0) * 1000
        comp_queries += sum(counting.query_counts.values())
        breakdown = dict(counting.query_counts)

    print(f"\nmaterialized: {hfid_mat!r}  queries/call={mat_queries / _ITERS:.2f}  ~{mat_ms:.3f} ms/call", flush=True)
    print(f"computed    : {hfid_comp!r}  queries/call={comp_queries / _ITERS:.2f}  ~{comp_ms / _ITERS:.3f} ms/call", flush=True)
    print(f"per-call query breakdown (computed): {breakdown}", flush=True)

    # Same result either way -- the "Jack" component can only come from resolving the owner.
    assert hfid_mat == ["Jack", "Rocky"]
    assert hfid_comp == ["Jack", "Rocky"]

    # Materialized read touches the DB zero times; the computed fallback must hit it.
    assert mat_queries == 0
    assert comp_queries >= 1
