from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import CoreGeneratorInstance
from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig
from prefect import flow, task
from prefect.cache_policies import NONE

from infrahub import lock
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.generators.models import (
    ProposedChangeGeneratorDefinition,
    RequestGeneratorDefinitionRun,
    RequestGeneratorRun,
)
from infrahub.git.base import extract_repo_file_information
from infrahub.git.repository import get_initialized_repo
from infrahub.services import InfrahubServices, services
from infrahub.workflows.catalogue import REQUEST_GENERATOR_DEFINITION_RUN, REQUEST_GENERATOR_RUN
from infrahub.workflows.utils import add_branch_tag


@flow(
    name="generator-run",
    flow_run_name="Run generator {model.generator_definition.definition_name} for {model.target_name}",
)
async def run_generator(model: RequestGeneratorRun) -> None:
    service = services.service

    await add_branch_tag(branch_name=model.branch_name)

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
    except ModuleImportError:
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
    except Exception:  # pylint: disable=broad-exception-caught
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value

    await generator_instance.update(do_full_update=True)


@task(name="generator-define-instance", task_run_name="Define Instance", cache_policy=NONE)
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


@flow(name="generator_definition_run", flow_run_name="Run all generators")
async def run_generator_definition(branch: str) -> None:
    service = services.service

    await add_branch_tag(branch_name=branch)

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
        await service.workflow.submit_workflow(workflow=REQUEST_GENERATOR_DEFINITION_RUN, parameters={"model": model})


@flow(
    name="request_generator_definition_run",
    flow_run_name="Execute generator {model.generator_definition.definition_name}",
)
async def request_generator_definition_run(model: RequestGeneratorDefinitionRun) -> None:
    service = services.service

    await add_branch_tag(branch_name=model.branch)

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

    for relationship in group.members.peers:
        member = relationship.peer
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
        await service.workflow.submit_workflow(
            workflow=REQUEST_GENERATOR_RUN, parameters={"model": request_generator_run_model}
        )
