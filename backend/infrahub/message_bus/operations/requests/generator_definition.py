from typing import List, Optional

from infrahub_sdk import UUIDT

from infrahub.core.constants import InfrahubKind, ValidatorConclusion, ValidatorState
from infrahub.core.timestamp import Timestamp
from infrahub.message_bus import InfrahubMessage, Meta, messages
from infrahub.services import InfrahubServices


async def check(message: messages.RequestGeneratorDefinitionCheck, service: InfrahubServices) -> None:
    async with service.task_report(
        title=f"Generator Definition: {message.generator_definition.definition_name}",
        related_node=message.proposed_change,
    ) as task_report:
        service.log.info(
            "Validating Generator selection",
            generator_definition=message.generator_definition.definition_id,
            source_branch=message.source_branch,
        )
        events: List[InfrahubMessage] = []

        proposed_change = await service.client.get(kind=InfrahubKind.PROPOSEDCHANGE, id=message.proposed_change)

        validator_name = f"Generator Validator: {message.generator_definition.definition_name}"
        validator_execution_id = str(UUIDT())
        check_execution_ids: List[str] = []

        await proposed_change.validations.fetch()

        validator = None
        for relationship in proposed_change.validations.peers:
            existing_validator = relationship.peer
            if (
                existing_validator.typename == InfrahubKind.GENERATORVALIDATOR
                and existing_validator.definition.id == message.generator_definition.definition_id
            ):
                validator = existing_validator

        if validator:
            validator.conclusion.value = ValidatorConclusion.UNKNOWN.value
            validator.state.value = ValidatorState.QUEUED.value
            validator.started_at.value = ""
            validator.completed_at.value = ""
            await validator.save()
        else:
            validator = await service.client.create(
                kind=InfrahubKind.GENERATORVALIDATOR,
                data={
                    "label": validator_name,
                    "proposed_change": message.proposed_change,
                    "definition": message.generator_definition.definition_id,
                },
            )
            await validator.save()

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

        for relationship in group.members.peers:
            member = relationship.peer
            generator_instance = instance_by_member.get(member.id)
            if _run_generator(
                instance_id=generator_instance,
                managed_branch=message.source_branch_sync_with_git,
                impacted_instances=impacted_instances,
            ):
                check_execution_id = str(UUIDT())
                check_execution_ids.append(check_execution_id)
                requested_instances += 1
                events.append(
                    messages.CheckGeneratorRun(
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
                        target_name=member.name.value,
                        validator_id=validator.id,
                        meta=Meta(validator_execution_id=validator_execution_id, check_execution_id=check_execution_id),
                    )
                )

        checks_in_execution = ",".join(check_execution_ids)
        await service.cache.set(
            key=f"validator_execution_id:{validator_execution_id}:checks", value=checks_in_execution, expires=7200
        )
        events.append(
            messages.FinalizeValidatorExecution(
                start_time=Timestamp().to_string(),
                validator_id=validator.id,
                validator_execution_id=validator_execution_id,
                validator_type=InfrahubKind.GENERATORVALIDATOR,
            )
        )
        await task_report.info(event=f"{requested_instances} generator instances required to be executed.")
        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)


async def run(message: messages.RequestGeneratorDefinitionRun, service: InfrahubServices) -> None:
    async with service.task_report(
        title="Executing Generator",
        related_node=message.generator_definition.definition_id,
    ) as task_report:
        service.log.info(
            "Received request to run generator",
            branch=message.branch,
            generator_definition=message.generator_definition.definition_id,
        )
        events: List[InfrahubMessage] = []

        group = await service.client.get(
            kind=InfrahubKind.GENERICGROUP,
            prefetch_relationships=True,
            populate_store=True,
            id=message.generator_definition.group_id,
            branch=message.branch,
        )
        await group.members.fetch()

        existing_instances = await service.client.filters(
            kind=InfrahubKind.GENERATORINSTANCE,
            definition__ids=[message.generator_definition.definition_id],
            include=["object"],
            branch=message.branch,
        )
        instance_by_member = {}
        for instance in existing_instances:
            instance_by_member[instance.object.peer.id] = instance.id

        repository = await service.client.get(
            kind=InfrahubKind.REPOSITORY, branch=message.branch, id=message.generator_definition.repository_id
        )

        for relationship in group.members.peers:
            member = relationship.peer
            generator_instance = instance_by_member.get(member.id)
            events.append(
                messages.RequestGeneratorRun(
                    generator_definition=message.generator_definition,
                    commit=repository.commit.value,
                    generator_instance=generator_instance,
                    repository_id=repository.id,
                    repository_name=repository.name.value,
                    repository_kind=repository.typename,
                    branch_name=message.branch,
                    query=message.generator_definition.query_name,
                    variables=member.extract(params=message.generator_definition.parameters),
                    target_id=member.id,
                    target_name=member.name.value,
                )
            )

        await task_report.info(
            event=f"Generator triggered for {len(group.members.peers)} members in {group.name.value}."
        )

        for event in events:
            event.assign_meta(parent=message)
            await service.send(message=event)


def _run_generator(instance_id: Optional[str], managed_branch: bool, impacted_instances: list[str]) -> bool:
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
