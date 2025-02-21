from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import CoreGeneratorInstance
from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig
from prefect import State, flow, task
from prefect.cache_policies import NONE
from prefect.states import Completed, Failed

from infrahub import lock
from infrahub.context import InfrahubContext  # noqa: TC001 needed for prefect flow
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.generators.models import (
    ProposedChangeGeneratorDefinition,
    RequestGeneratorDefinitionRun,
    RequestGeneratorRun,
)
from infrahub.git.base import extract_repo_file_information
from infrahub.git.repository import get_initialized_repo
from infrahub.services import InfrahubServices  # noqa: TC001 needed for prefect flow
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN, REQUEST_GENERATOR_RUN
from infrahub.workflows.utils import add_tags

if TYPE_CHECKING:
    from collections.abc import Coroutine


@flow(
    name="generator-run",
    flow_run_name="Run generator {model.generator_definition.definition_name}",
)
async def run_generator(model: RequestGeneratorRun, service: InfrahubServices) -> None:
    await add_tags(branches=[model.branch_name], nodes=[model.target_id])

    repository = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
        commit=model.commit,
    )

    generator_definition = InfrahubGeneratorDefinitionConfig(
        name=model.generator_definition.definition_name,
        class_name=model.generator_definition.class_name,
        file_path=model.generator_definition.file_path,
        query=model.generator_definition.query_name,
        targets=model.generator_definition.group_id,
        convert_query_response=model.generator_definition.convert_query_response,
    )

    commit_worktree = repository.get_commit_worktree(commit=model.commit)

    file_info = extract_repo_file_information(
        full_filename=commit_worktree.directory / generator_definition.file_path,
        repo_directory=repository.directory_root,
        worktree_directory=commit_worktree.directory,
    )
    generator_instance = await _define_instance(model=model, service=service)

    try:
        generator_class = generator_definition.load_class(
            import_root=repository.directory_root, relative_path=file_info.relative_repo_path_dir
        )

        generator = generator_class(
            query=generator_definition.query,
            client=service.client,
            branch=model.branch_name,
            params=model.variables,
            generator_instance=generator_instance.id,
            convert_query_response=generator_definition.convert_query_response,
            infrahub_node=InfrahubNode,
        )
        await generator.run(identifier=generator_definition.name)
        generator_instance.status.value = GeneratorInstanceStatus.READY.value
    except (ModuleImportError, Exception):  # pylint: disable=broad-exception-caught
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        await generator_instance.update(do_full_update=True)
        raise

    await generator_instance.update(do_full_update=True)


@task(name="generator-define-instance", task_run_name="Define Instance", cache_policy=NONE)  # type: ignore[arg-type]
async def _define_instance(model: RequestGeneratorRun, service: InfrahubServices) -> CoreGeneratorInstance:
    if model.generator_instance:
        instance = await service.client.get(
            kind=CoreGeneratorInstance, id=model.generator_instance, branch=model.branch_name
        )
        instance.status.value = GeneratorInstanceStatus.PENDING.value
        await instance.update(do_full_update=True)

    else:
        async with lock.registry.get(
            f"{model.target_id}-{model.generator_definition.definition_id}", namespace="generator"
        ):
            instances = await service.client.filters(
                kind=CoreGeneratorInstance,
                definition__ids=[model.generator_definition.definition_id],
                object__ids=[model.target_id],
                branch=model.branch_name,
            )
            if instances:
                instance = instances[0]
                instance.status.value = GeneratorInstanceStatus.PENDING.value
                await instance.update(do_full_update=True)
            else:
                instance = await service.client.create(
                    kind=CoreGeneratorInstance,
                    branch=model.branch_name,
                    data={
                        "name": f"{model.generator_definition.definition_name}: {model.target_name}",
                        "status": GeneratorInstanceStatus.PENDING.value,
                        "object": model.target_id,
                        "definition": model.generator_definition.definition_id,
                    },
                )
                await instance.save()
    return instance


@flow(name="generator-definition-run", flow_run_name="Run all generators")
async def run_generator_definition(branch: str, context: InfrahubContext, service: InfrahubServices) -> None:
    await add_tags(branches=[branch])

    generators = await service.client.filters(
        kind=InfrahubKind.GENERATORDEFINITION, prefetch_relationships=True, populate_store=True, branch=branch
    )

    generator_definitions = [
        ProposedChangeGeneratorDefinition(
            definition_id=generator.id,
            definition_name=generator.name.value,
            class_name=generator.class_name.value,
            file_path=generator.file_path.value,
            query_name=generator.query.peer.name.value,
            query_models=generator.query.peer.models.value,
            repository_id=generator.repository.peer.id,
            parameters=generator.parameters.value,
            group_id=generator.targets.peer.id,
            convert_query_response=generator.convert_query_response.value,
        )
        for generator in generators
    ]

    for generator_definition in generator_definitions:
        model = RequestGeneratorDefinitionRun(branch=branch, generator_definition=generator_definition)
        await service.workflow.submit_workflow(
            workflow=REQUEST_GENERATOR_DEFINITION_RUN, context=context, parameters={"model": model}
        )


@flow(
    name="request-generator-definition-run",
    flow_run_name="Execute generator {model.generator_definition.definition_name}",
)
async def request_generator_definition_run(
    model: RequestGeneratorDefinitionRun, context: InfrahubContext, service: InfrahubServices
) -> State[Any]:
    await add_tags(branches=[model.branch], nodes=[model.generator_definition.definition_id])

    group = await service.client.get(
        kind=InfrahubKind.GENERICGROUP,
        prefetch_relationships=True,
        populate_store=True,
        id=model.generator_definition.group_id,
        branch=model.branch,
    )
    await group.members.fetch()

    existing_instances = await service.client.filters(
        kind=InfrahubKind.GENERATORINSTANCE,
        definition__ids=[model.generator_definition.definition_id],
        include=["object"],
        branch=model.branch,
    )
    instance_by_member = {}
    for instance in existing_instances:
        instance_by_member[instance.object.peer.id] = instance.id

    repository = await service.client.get(
        kind=InfrahubKind.REPOSITORY,
        branch=model.branch,
        id=model.generator_definition.repository_id,
        raise_when_missing=False,
    )
    if not repository:
        repository = await service.client.get(
            kind=InfrahubKind.READONLYREPOSITORY,
            branch=model.branch,
            id=model.generator_definition.repository_id,
            raise_when_missing=True,
        )

    tasks: list[Coroutine[Any, Any, Any]] = []
    for relationship in group.members.peers:
        member = relationship.peer

        if model.target_members and member.id not in model.target_members:
            continue

        generator_instance = instance_by_member.get(member.id)
        request_generator_run_model = RequestGeneratorRun(
            generator_definition=model.generator_definition,
            commit=repository.commit.value,
            generator_instance=generator_instance,
            repository_id=repository.id,
            repository_name=repository.name.value,
            repository_kind=repository.typename,
            branch_name=model.branch,
            query=model.generator_definition.query_name,
            variables=member.extract(params=model.generator_definition.parameters),
            target_id=member.id,
            target_name=member.display_label,
        )
        tasks.append(
            service.workflow.execute_workflow(
                workflow=REQUEST_GENERATOR_RUN, context=context, parameters={"model": request_generator_run_model}
            )
        )

    try:
        await asyncio.gather(*tasks)
        return Completed(message=f"Successfully run {len(tasks)} generators")
    except Exception as exc:
        return Failed(message="One or more generators failed", error=exc)
