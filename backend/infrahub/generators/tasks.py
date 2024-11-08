import os

from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.protocols import CoreGeneratorInstance
from infrahub_sdk.schema import InfrahubGeneratorDefinitionConfig
from prefect import flow, task

from infrahub import lock
from infrahub.core.constants import GeneratorInstanceStatus
from infrahub.generators.models import RequestGeneratorRun
from infrahub.git.base import extract_repo_file_information
from infrahub.git.repository import get_initialized_repo
from infrahub.services import InfrahubServices, services


@flow(name="generator-run")
async def run_generator(model: RequestGeneratorRun) -> None:
    service = services.service

    repository = await get_initialized_repo(
        repository_id=model.repository_id,
        name=model.repository_name,
        service=service,
        repository_kind=model.repository_kind,
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
        full_filename=os.path.join(commit_worktree.directory, generator_definition.file_path.as_posix()),
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


@task
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
