from dataclasses import dataclass, field

from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, PathType, SchemaPathType
from infrahub.core.path import SchemaPath
from infrahub.core.schema import NodeSchema, SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.pool.overlap import UniqueAttributePoolOverlapChecker
from infrahub.core.validators.pool.scope_dependency import ScopeViolationBuilder
from infrahub.pools.number_pool_overlap import PoolRangeSet
from infrahub.pools.number_pool_range_validation import NumberRangeBounds
from tests.helpers.schema import SHARED_NUMBER_TICKET, TICKET

BRANCH = Branch(name="feature")


@dataclass
class RecordingAttributePools:
    pools: list[PoolRangeSet]
    reads: list[tuple[str, str]] = field(default_factory=list)

    async def get_attribute_pool_ranges(self, kind: str, attribute_name: str) -> list[PoolRangeSet]:
        self.reads.append((kind, attribute_name))
        return self.pools


def ticket_request(ticket: NodeSchema) -> SchemaConstraintValidatorRequest:
    schema_branch = SchemaBranch(cache={}, name=BRANCH.name)
    schema_branch.load_schema(schema=SchemaRoot(nodes=[ticket]))
    schema_branch.process()
    node_schema = schema_branch.get_node(name=ticket.kind, duplicate=False)
    return SchemaConstraintValidatorRequest(
        branch=BRANCH,
        constraint_name="attribute.unique.update",
        node_schema=node_schema,
        schema_path=SchemaPath(path_type=SchemaPathType.ATTRIBUTE, schema_kind=ticket.kind, field_name="ticket_id"),
        schema_branch=schema_branch,
    )


async def test_making_an_attribute_unique_is_refused_for_each_pool_overlapping_another() -> None:
    pools = RecordingAttributePools(
        pools=[
            PoolRangeSet(pool_id="pool-b", pool_name="tickets-b", ranges=[NumberRangeBounds(start=5, end=15)]),
            PoolRangeSet(pool_id="pool-a", pool_name="tickets-a", ranges=[NumberRangeBounds(start=1, end=10)]),
            PoolRangeSet(pool_id="pool-c", pool_name="tickets-c", ranges=[NumberRangeBounds(start=20, end=30)]),
        ]
    )
    checker = UniqueAttributePoolOverlapChecker(pool_reader=pools, violation_builder=ScopeViolationBuilder())

    grouped_data_paths = await checker.check(ticket_request(ticket=TICKET))

    data_paths = [path for grouped in grouped_data_paths for path in grouped.get_all_data_paths()]
    assert [(path.node_id, path.value) for path in data_paths] == [
        (
            "pool-a",
            "The 'tickets-a' pool cannot share numbers with another pool on the unique attribute 'ticket_id': "
            "1 - 10 overlaps 5 - 15 of the 'tickets-b' pool. Choose ranges that no other pool on 'ticket_id' uses.",
        ),
        (
            "pool-b",
            "The 'tickets-b' pool cannot share numbers with another pool on the unique attribute 'ticket_id': "
            "5 - 15 overlaps 1 - 10 of the 'tickets-a' pool. Choose ranges that no other pool on 'ticket_id' uses.",
        ),
    ]
    assert {(path.branch, path.path_type, path.kind, path.field_name) for path in data_paths} == {
        (BRANCH.name, PathType.NODE, InfrahubKind.NUMBERPOOL, "ticket_id")
    }
    assert pools.reads == [(TICKET.kind, "ticket_id")]


async def test_pools_that_do_not_overlap_let_the_attribute_become_unique() -> None:
    pools = RecordingAttributePools(
        pools=[
            PoolRangeSet(pool_id="pool-a", pool_name="tickets-a", ranges=[NumberRangeBounds(start=1, end=10)]),
            PoolRangeSet(pool_id="pool-b", pool_name="tickets-b", ranges=[NumberRangeBounds(start=11, end=20)]),
        ]
    )
    checker = UniqueAttributePoolOverlapChecker(pool_reader=pools, violation_builder=ScopeViolationBuilder())

    assert await checker.check(ticket_request(ticket=TICKET)) == []
    assert pools.reads == [(TICKET.kind, "ticket_id")]


async def test_an_attribute_left_shared_reads_no_pool() -> None:
    pools = RecordingAttributePools(
        pools=[
            PoolRangeSet(pool_id="pool-a", pool_name="tickets-a", ranges=[NumberRangeBounds(start=1, end=10)]),
            PoolRangeSet(pool_id="pool-b", pool_name="tickets-b", ranges=[NumberRangeBounds(start=5, end=15)]),
        ]
    )
    checker = UniqueAttributePoolOverlapChecker(pool_reader=pools, violation_builder=ScopeViolationBuilder())

    assert await checker.check(ticket_request(ticket=SHARED_NUMBER_TICKET)) == []
    assert pools.reads == []
