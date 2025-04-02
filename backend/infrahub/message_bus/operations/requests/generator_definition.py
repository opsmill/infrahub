from infrahub_sdk.protocols import CoreGeneratorValidator
from prefect import flow
from prefect.logging import get_run_logger

from infrahub.core.constants import InfrahubKind, ValidatorConclusion
from infrahub.core.validators.checks_runner import run_checks_and_update_validator
from infrahub.message_bus import messages
from infrahub.proposed_change.models import RunGeneratorAsCheckModel
from infrahub.services import InfrahubServices
from infrahub.validators.tasks import start_validator
from infrahub.workflows.catalogue import RUN_GENERATOR_AS_CHECK
from infrahub.workflows.utils import add_tags


@flow(
    name="generator-definition-check",
    flow_run_name="Validate Generator selection for {message.generator_definition.definition_name}",
)
async def check(message: messages.RequestGeneratorDefinitionCheck, service: InfrahubServices) -> None:
    log = get_run_logger()
    await add_tags(branches=[message.source_branch], nodes=[message.proposed_change])

    proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

    validator_name = f"Generator Validator: {message.generator_definition.definition_name}"
    await proposed_change.validations.fetch()

    previous_validator: CoreGeneratorValidator | None = None
    for relationship in proposed_change.validations.peers:
        existing_validator = relationship.peer
        if (
            existing_validator.typename == InfrahubKind.GENERATORVALIDATOR
            and existing_validator.definition.id == message.generator_definition.definition_id
        ):
            previous_validator = existing_validator

    validator = await start_validator(
        service=service,
        validator=previous_validator,
        validator_type=CoreGeneratorValidator,
        proposed_change=message.proposed_change,
        data={
            "label": validator_name,
            "definition": message.generator_definition.definition_id,
        },
        context=message.context,
    )

    group = await service.client.get(
        kind=InfrahubKind.GENERICGROUP,
        prefetch_relationships=True,
        populate_store=True,
        id=message.generator_definition.group_id,
        branch=message.source_branch,
    )
    await group.members.fetch()

    existing_instances = await service.client.filters(
        kind=InfrahubKind.GENERATORINSTANCE,
        definition__ids=[message.generator_definition.definition_id],
        include=["object"],
        branch=message.source_branch,
    )
    instance_by_member = {}
    for instance in existing_instances:
        instance_by_member[instance.object.peer.id] = instance.id

    repository = message.branch_diff.get_repository(repository_id=message.generator_definition.repository_id)
    requested_instances = 0
    impacted_instances = message.branch_diff.get_subscribers_ids(kind=InfrahubKind.GENERATORINSTANCE)

    check_generator_run_models = []
    for relationship in group.members.peers:
        member = relationship.peer
        generator_instance = instance_by_member.get(member.id)
        if _run_generator(
            instance_id=generator_instance,
            managed_branch=message.source_branch_sync_with_git,
            impacted_instances=impacted_instances,
        ):
            requested_instances += 1
            log.info(f"Trigger execution of {message.generator_definition.definition_name} for {member.display_label}")
            check_generator_run_model = RunGeneratorAsCheckModel(
                context=message.context,
                generator_definition=message.generator_definition,
                generator_instance=generator_instance,
                commit=repository.source_commit,
                repository_id=repository.repository_id,
                repository_name=repository.repository_name,
                repository_kind=repository.kind,
                branch_name=message.source_branch,
                query=message.generator_definition.query_name,
                variables=member.extract(params=message.generator_definition.parameters),
                target_id=member.id,
                target_name=member.display_label,
                validator_id=validator.id,
                proposed_change=message.proposed_change,
            )
            check_generator_run_models.append(check_generator_run_model)

    checks_coroutines = [
        service.workflow.execute_workflow(
            workflow=RUN_GENERATOR_AS_CHECK,
            parameters={"model": check_generator_run_model},
            expected_return=ValidatorConclusion,
        )
        for check_generator_run_model in check_generator_run_models
    ]

    await run_checks_and_update_validator(
        checks=checks_coroutines,
        validator=validator,
        context=message.context,
        service=service,
        proposed_change_id=proposed_change.id,
    )


def _run_generator(instance_id: str | None, managed_branch: bool, impacted_instances: list[str]) -> bool:
    """Returns a boolean to indicate if a generator instance needs to be executed
    Will return true if:
        * The instance_id wasn't set which could be that it's a new object that doesn't have a previous generator instance
        * The source branch is set to sync with Git which would indicate that it could contain updates in git to the generator
        * The instance_id exists in the impacted_instances list
    Will return false if:
        * The source branch is a not one that syncs with git and the instance_id exists and is not in the impacted list
    """
    if not instance_id or managed_branch:
        return True
    return instance_id in impacted_instances
