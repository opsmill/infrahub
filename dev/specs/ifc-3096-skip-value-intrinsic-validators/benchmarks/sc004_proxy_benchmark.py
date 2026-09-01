# ruff: noqa: INP001  # standalone measurement script, not a package module
"""Proxy benchmark for the constraint-validation stage of a data-only branch operation.

Not collected by the suite. To run it, copy this file into
`backend/tests/component/core/constraint_validators/` and invoke:

    BENCH_POPULATION=2000 BENCH_REPEATS=5 INFRAHUB_USE_TEST_CONTAINERS=false \
        uv run pytest <copied path> -p no:randomly -q -s --timeout=1800

See `measurement-sc-004.md` in the parent directory for what it measures and what it does not.
"""

import os
import statistics
import time

from infrahub.core.branch import Branch
from infrahub.core.diff.model.path import NodeDiffFieldSummary
from infrahub.core.node import Node
from infrahub.core.schema import GenericSchema, NodeSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.validators.attribute.choices import AttributeChoicesChecker
from infrahub.core.validators.attribute.enum import AttributeEnumChecker
from infrahub.core.validators.attribute.kind import AttributeKindChecker
from infrahub.core.validators.attribute.length import AttributeLengthChecker
from infrahub.core.validators.attribute.min_max import AttributeNumberChecker
from infrahub.core.validators.attribute.optional import AttributeOptionalChecker
from infrahub.core.validators.attribute.regex import AttributeRegexChecker
from infrahub.core.validators.determiner import build_constraint_validator_determiner
from infrahub.core.validators.model import SchemaConstraintValidatorRequest
from infrahub.core.validators.relationship.peer import RelationshipPeerChecker
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from infrahub.dependencies.interface import DependencyBuilderContext

FLIPPED_CHECKERS = (
    AttributeKindChecker,
    AttributeOptionalChecker,
    AttributeRegexChecker,
    AttributeLengthChecker,
    AttributeEnumChecker,
    AttributeChoicesChecker,
    AttributeNumberChecker,
    RelationshipPeerChecker,
)

POPULATION = int(os.environ.get("BENCH_POPULATION", "1000"))
REPEATS = int(os.environ.get("BENCH_REPEATS", "3"))


async def _populate(db: InfrahubDatabase, branch: Branch, n_cars: int) -> list[str]:
    n_people = max(n_cars // 10, 1)
    people = []
    for i in range(n_people):
        p = await Node.init(db=db, schema="TestPerson", branch=branch)
        await p.new(db=db, name=f"person-{i}", height=160 + (i % 40))
        await p.save(db=db)
        people.append(p)

    car_ids = []
    for i in range(n_cars):
        c = await Node.init(db=db, schema="TestCar", branch=branch)
        await c.new(
            db=db,
            name=f"car-{i}",
            nbr_seats=(i % 5) + 1,
            color="#abcdef",
            is_electric=bool(i % 2),
            transmission="manual",
            owner=people[i % n_people].id,
            driver=people[(i + 1) % n_people].id,
        )
        await c.save(db=db)
        car_ids.append(c.id)
    return car_ids


def _node_diffs(changed_car_uuids: list[str]) -> list[NodeDiffFieldSummary]:
    changed = set(changed_car_uuids)
    return [
        NodeDiffFieldSummary(
            kind="TestCar",
            attribute_node_uuids={
                "name": set(changed),
                "nbr_seats": set(changed),
                "color": set(changed),
                "is_electric": set(changed),
                "transmission": set(changed),
            },
            relationship_node_uuids={"driver": set(changed)},
        ),
        NodeDiffFieldSummary(kind="TestPerson", attribute_node_uuids={"height": set()}),
    ]


async def _run_once(
    db: InfrahubDatabase, branch: Branch, schema_branch: SchemaBranch, node_diffs: list[NodeDiffFieldSummary]
) -> tuple[float, int]:
    start = time.perf_counter()
    determiner = build_constraint_validator_determiner(db=db, branch=branch)
    constraints = await determiner.get_constraints(schema_branch=schema_branch, node_diffs=node_diffs)

    context = DependencyBuilderContext(db=db, branch=branch)
    checker = AggregatedSchemaConstraintsDependency.build(context=context)
    for constraint in constraints:
        schema = schema_branch.get(name=constraint.path.schema_kind, duplicate=False)
        if not isinstance(schema, GenericSchema | NodeSchema):
            continue
        request = SchemaConstraintValidatorRequest(
            branch=branch,
            constraint_name=constraint.constraint_name,
            node_schema=schema,
            schema_path=constraint.path,
            schema_branch=schema_branch,
            node_uuids=constraint.node_uuids,
        )
        await checker.run_constraints(request)
    return time.perf_counter() - start, len(constraints)


async def test_sc004_proxy(db: InfrahubDatabase, default_branch: Branch, car_person_schema: SchemaBranch) -> None:
    schema_branch = car_person_schema

    populate_start = time.perf_counter()
    car_ids = await _populate(db=db, branch=default_branch, n_cars=POPULATION)
    populate_seconds = time.perf_counter() - populate_start

    node_diffs = _node_diffs(changed_car_uuids=car_ids[:5])

    after_times: list[float] = []
    before_times: list[float] = []
    after_count = before_count = 0

    def _set_before(enabled: bool) -> None:
        for cls in FLIPPED_CHECKERS:
            cls.triggered_by_data_change = enabled

    try:
        # discard a warm-up round in each mode so query-plan caching does not land on one side
        for enabled in (True, False):
            _set_before(enabled)
            await _run_once(db=db, branch=default_branch, schema_branch=schema_branch, node_diffs=node_diffs)

        for _ in range(REPEATS):
            _set_before(True)
            seconds, before_count = await _run_once(
                db=db, branch=default_branch, schema_branch=schema_branch, node_diffs=node_diffs
            )
            before_times.append(seconds)

            _set_before(False)
            seconds, after_count = await _run_once(
                db=db, branch=default_branch, schema_branch=schema_branch, node_diffs=node_diffs
            )
            after_times.append(seconds)
    finally:
        _set_before(False)

    print("\n=== SC-004 PROXY MEASUREMENT ===")
    print(f"population: {POPULATION} TestCar + {max(POPULATION // 10, 1)} TestPerson nodes")
    print(f"population build time: {populate_seconds:.2f}s")
    print(f"repeats: {REPEATS}")
    print(f"BEFORE (checkers reverted to triggered_by_data_change=True): constraints={before_count}")
    print(f"  times: {[round(t, 4) for t in before_times]}")
    print(f"  median: {statistics.median(before_times):.4f}s  min: {min(before_times):.4f}s")
    print(f"AFTER  (checkers flipped to False): constraints={after_count}")
    print(f"  times: {[round(t, 4) for t in after_times]}")
    print(f"  median: {statistics.median(after_times):.4f}s  min: {min(after_times):.4f}s")
    reduction = 1 - (statistics.median(after_times) / statistics.median(before_times))
    print(f"REDUCTION (median): {reduction * 100:.1f}%")
    print("=== END SC-004 PROXY MEASUREMENT ===")
