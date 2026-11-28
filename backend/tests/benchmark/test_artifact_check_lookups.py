import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
from pytest_benchmark.fixture import BenchmarkFixture

from infrahub.core import registry
from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.initialization import create_default_branch, create_global_branch, create_root_node
from infrahub.core.manager import NodeManager
from infrahub.core.node import Node
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.core.utils import delete_all_nodes
from infrahub.database import InfrahubDatabase
from infrahub.proposed_change.artifact_retry import (
    UNRESOLVED_CHECK_CONCLUSIONS,
    ArtifactCheckState,
    ArtifactRunPlanner,
    ArtifactTarget,
)

NBR_WARMUP = int(os.getenv("INFRAHUB_BENCHMARK_NBR_WARMUP", "5"))
CHECK_COUNT = 1000
FAILED_CHECK_COUNT = 10
UNFINISHED_CHECK_COUNT = 2
OTHER_FAILED_CHECK_COUNT = 200
"""Failed checks of another proposed change on the same definition."""

PLANNED_TARGET_COUNT = 2000
PLANNED_UNRESOLVED_COUNT = 20


@dataclass
class ArtifactCheckData:
    validator_id: str


@pytest.fixture(scope="module")
async def reset_environment(db: InfrahubDatabase) -> None:
    registry.delete_all()
    await delete_all_nodes(db=db)
    await create_root_node(db=db)


@pytest.fixture(scope="module")
async def default_branch(reset_environment: None, db: InfrahubDatabase) -> Branch:
    branch = await create_default_branch(db=db)
    await create_global_branch(db=db)
    registry.schema = SchemaManager()
    return branch


@pytest.fixture(scope="module")
async def core_schema(db: InfrahubDatabase, default_branch: Branch) -> SchemaBranch:
    schema_branch = registry.schema.get_schema_branch(name=default_branch.name)
    schema_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_branch.load_schema(schema=SchemaRoot(**core_models))
    schema_branch.process()
    default_branch.update_schema_hash()
    await default_branch.save(db=db)
    return schema_branch


async def _create_validator(db: InfrahubDatabase, definition: Node, name: str) -> Node:
    proposed_change = await Node.init(db=db, schema=InfrahubKind.PROPOSEDCHANGE)
    await proposed_change.new(db=db, name=name, source_branch=f"{name}-branch", destination_branch="main")
    await proposed_change.save(db=db)
    validator = await Node.init(db=db, schema=InfrahubKind.ARTIFACTVALIDATOR)
    await validator.new(db=db, proposed_change=proposed_change, definition=definition)
    await validator.save(db=db)
    return validator


async def _create_checks(
    db: InfrahubDatabase, validator: Node, origin: str, conclusions: list[ValidatorConclusion]
) -> None:
    for index, conclusion in enumerate(conclusions):
        check = await Node.init(db=db, schema=InfrahubKind.ARTIFACTCHECK)
        await check.new(
            db=db,
            name=f"config: device-{index}",
            origin=origin,
            kind="ArtifactDefinition",
            validator=validator,
            conclusion=conclusion.value,
            artifact_id=f"artifact-{index}",
        )
        await check.save(db=db)


@pytest.fixture(scope="module")
async def artifact_check_data(
    db: InfrahubDatabase, default_branch: Branch, core_schema: SchemaBranch
) -> ArtifactCheckData:
    """A validator with `CHECK_COUNT` checks, few of them unresolved, and another validator with failed checks."""
    repository = await Node.init(db=db, schema=InfrahubKind.REPOSITORY)
    await repository.new(db=db, name="configurations", location="https://github.com/test/configurations.git")
    await repository.save(db=db)
    query = await Node.init(db=db, schema=InfrahubKind.GRAPHQLQUERY)
    await query.new(db=db, name="Devices", query="query { CoreRepository { edges { node { id } } } }")
    await query.save(db=db)
    transform = await Node.init(db=db, schema=InfrahubKind.TRANSFORMJINJA2)
    await transform.new(db=db, name="config", query=query, repository=repository, template_path="config.j2")
    await transform.save(db=db)
    group = await Node.init(db=db, schema=InfrahubKind.STANDARDGROUP)
    await group.new(db=db, name="devices")
    await group.save(db=db)
    definition = await Node.init(db=db, schema=InfrahubKind.ARTIFACTDEFINITION)
    await definition.new(
        db=db,
        name="config",
        artifact_name="config",
        content_type="text/plain",
        parameters={"value": {}},
        targets=group,
        transformation=transform,
    )
    await definition.save(db=db)

    validator = await _create_validator(db=db, definition=definition, name="retried")
    successful_count = CHECK_COUNT - FAILED_CHECK_COUNT - UNFINISHED_CHECK_COUNT
    await _create_checks(
        db=db,
        validator=validator,
        origin=repository.id,
        conclusions=[ValidatorConclusion.FAILURE] * FAILED_CHECK_COUNT
        + [ValidatorConclusion.UNKNOWN] * UNFINISHED_CHECK_COUNT
        + [ValidatorConclusion.SUCCESS] * successful_count,
    )
    other_validator = await _create_validator(db=db, definition=definition, name="other")
    await _create_checks(
        db=db,
        validator=other_validator,
        origin=repository.id,
        conclusions=[ValidatorConclusion.FAILURE] * OTHER_FAILED_CHECK_COUNT,
    )
    return ArtifactCheckData(validator_id=validator.id)


def test_unresolved_checks_of_a_validator(
    exec_async: Callable[..., Any],
    aio_benchmark: Callable[..., Any],
    db: InfrahubDatabase,
    default_branch: Branch,
    artifact_check_data: ArtifactCheckData,
) -> None:
    """Read the failed and unfinished checks of one validator, as each artifact validation run does."""
    filters = {
        "validator__ids": [artifact_check_data.validator_id],
        "conclusion__values": list(UNRESOLVED_CHECK_CONCLUSIONS),
    }
    result = exec_async(
        NodeManager.query, db=db, schema=InfrahubKind.ARTIFACTCHECK, filters=filters, branch=default_branch
    )
    assert len(result) == FAILED_CHECK_COUNT + UNFINISHED_CHECK_COUNT

    for _ in range(NBR_WARMUP):
        exec_async(NodeManager.query, db=db, schema=InfrahubKind.ARTIFACTCHECK, filters=filters, branch=default_branch)

    aio_benchmark(NodeManager.query, db=db, schema=InfrahubKind.ARTIFACTCHECK, filters=filters, branch=default_branch)


def test_plan_failed_retry_of_a_large_definition(benchmark: BenchmarkFixture) -> None:
    """Match unresolved checks to the targets of a large definition, half of them by artifact and half by name."""
    targets = [
        ArtifactTarget(target_id=f"device-{index}", label=f"device-{index}", artifact_id=f"artifact-{index}")
        for index in range(PLANNED_TARGET_COUNT)
    ]
    unresolved_checks = [
        ArtifactCheckState(
            check_id=f"check-{index}",
            artifact_id=f"artifact-{index}" if index % 2 else None,
            name=f"config: device-{index}",
            conclusion=ValidatorConclusion.FAILURE.value,
        )
        for index in range(PLANNED_UNRESOLVED_COUNT)
    ]

    def plan() -> list[str]:
        planner = ArtifactRunPlanner(artifact_name="config", targets=targets, unresolved_checks=unresolved_checks)
        return planner.plan_failed_retry(requested_checks=None).target_ids

    assert len(benchmark(plan)) == PLANNED_UNRESOLVED_COUNT
