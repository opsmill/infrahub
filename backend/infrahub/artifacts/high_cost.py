from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from infrahub import config
from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.graphql.cost.render_cost import RenderCostClassifier
from infrahub.workers.dependencies import get_workflow
from infrahub.workflows.catalogue import GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from infrahub_sdk import InfrahubClient

    from infrahub.artifacts.models import CheckArtifactCreate
    from infrahub.context import InfrahubContext
    from infrahub.graphql.cost.render_cost import RenderCost


@dataclass(frozen=True, slots=True)
class StartedCheck:
    conclusion: Coroutine[Any, None, ValidatorConclusion]
    in_sequence: bool
    """The check renders a high-cost artifact and runs in a sequence of high-cost checks."""


async def build_render_cost_classifier(
    client: InfrahubClient, branch_name: str, query_id: str, query: str
) -> RenderCostClassifier:
    """Prepare the classification of the renders of a stored query, reading its cost level only when needed."""
    cost_level = None
    if config.SETTINGS.graphql_cost.limit_high_cost_renders:
        stored_query = await client.get(kind=InfrahubKind.GRAPHQLQUERY, id=query_id, branch=branch_name)
        cost_level = stored_query.cost_level.value
    return await RenderCostClassifier.for_stored_query(branch_name=branch_name, query=query, cost_level=cost_level)


def start_artifact_check(
    client: InfrahubClient, model: CheckArtifactCreate, render_cost: RenderCost, context: InfrahubContext
) -> StartedCheck:
    """Prepare the check of one artifact: a skipped check, or the render of the artifact."""
    if render_cost.high_cost and config.SETTINGS.graphql_cost.skip_high_cost_artifact_checks:
        return StartedCheck(
            conclusion=record_skipped_artifact_check(
                client=client, model=model, worst_case_database_rows=render_cost.worst_case_database_rows
            ),
            in_sequence=False,
        )
    return StartedCheck(
        conclusion=get_workflow().execute_workflow(
            workflow=GIT_REPOSITORIES_CHECK_ARTIFACT_CREATE,
            context=context,
            parameters={"model": model},
            expected_return=ValidatorConclusion,
        ),
        in_sequence=render_cost.high_cost,
    )


def skipped_check_message(query_name: str, worst_case_database_rows: int | None) -> str:
    limit = config.SETTINGS.graphql_cost.high_cost_database_rows
    if worst_case_database_rows is None:
        estimate = "could not be estimated for this target"
    else:
        estimate = f"is estimated at {worst_case_database_rows:,} worst-case database rows for this target"
    return (
        f"Not rendered: one run of the query {query_name} {estimate}, and the limit is {limit:,}. "
        "Infrahub generates this artifact after the merge."
    )


async def record_skipped_artifact_check(
    client: InfrahubClient, model: CheckArtifactCreate, worst_case_database_rows: int | None
) -> ValidatorConclusion:
    """Save the check of an artifact that the validator did not render because of its estimated cost."""
    check_name = f"{model.artifact_name}: {model.target_name}"
    data = {
        "created_at": Timestamp().to_string(),
        "message": skipped_check_message(query_name=model.query, worst_case_database_rows=worst_case_database_rows),
        "conclusion": ValidatorConclusion.SKIPPED.value,
        "severity": "info",
        "changed": None,
        "checksum": None,
        "artifact_id": model.artifact_id,
        "storage_id": None,
    }
    existing_checks = await client.filters(
        kind=InfrahubKind.ARTIFACTCHECK, validator__ids=model.validator_id, name__value=check_name
    )
    if existing_checks:
        check = existing_checks[0]
        for name, value in data.items():
            getattr(check, name).value = value
    else:
        check = await client.create(
            kind=InfrahubKind.ARTIFACTCHECK,
            data={
                "name": check_name,
                "origin": model.repository_id,
                "kind": "ArtifactDefinition",
                "validator": model.validator_id,
                **data,
            },
        )
    await check.save()
    return ValidatorConclusion.SKIPPED


async def _run_in_sequence(checks: list[Coroutine[Any, None, ValidatorConclusion]]) -> ValidatorConclusion:
    conclusion = ValidatorConclusion.SUCCESS
    for check in checks:
        if await check == ValidatorConclusion.FAILURE:
            conclusion = ValidatorConclusion.FAILURE
    return conclusion


def checks_in_sequences(
    checks: list[Coroutine[Any, None, ValidatorConclusion]],
) -> list[Coroutine[Any, None, ValidatorConclusion]]:
    """Group high-cost checks into as many sequences as renders that can hold a slot at once.

    Each check waits for a slot of the high-cost renders; running them in sequences keeps the checks that wait
    for a slot from taking the task workers that the other checks need. A sequence concludes as a failure when
    one of its checks fails.
    """
    sequences = config.SETTINGS.graphql_cost.high_cost_renders_at_once
    return [_run_in_sequence(checks[index::sequences]) for index in range(sequences) if checks[index::sequences]]
