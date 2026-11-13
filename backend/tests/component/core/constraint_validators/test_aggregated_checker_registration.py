from infrahub.core.branch import Branch
from infrahub.core.validators import CONSTRAINT_VALIDATOR_MAP
from infrahub.database import InfrahubDatabase
from infrahub.dependencies.builder.constraint.schema.aggregated import AggregatedSchemaConstraintsDependency
from infrahub.dependencies.interface import DependencyBuilderContext


async def test_every_mapped_checker_is_run(db: InfrahubDatabase, default_branch: Branch) -> None:
    aggregated = AggregatedSchemaConstraintsDependency.build(
        context=DependencyBuilderContext(db=db, branch=default_branch)
    )

    registered = {type(checker) for checker in aggregated.constraints}
    mapped = {checker for checker in CONSTRAINT_VALIDATOR_MAP.values() if checker is not None}
    assert mapped - registered == set()
