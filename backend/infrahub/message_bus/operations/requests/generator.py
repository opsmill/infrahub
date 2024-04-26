import os

from infrahub_sdk import InfrahubNode
from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.schema import InfrahubGeneratorDefinitionConfig

from infrahub import lock
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind
from infrahub.git.repository import extract_repo_file_information, get_initialized_repo
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices


async def run(message: messages.RequestGeneratorRun, service: InfrahubServices):
    repository = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    generator_definition = InfrahubGeneratorDefinitionConfig(
        name=message.generator_definition.definition_name,
        class_name=message.generator_definition.class_name,
        file_path=message.generator_definition.file_path,
        query=message.generator_definition.query_name,
        targets=message.generator_definition.group_id,
        convert_query_response=message.generator_definition.convert_query_response,
    )

    commit_worktree = repository.get_commit_worktree(commit=message.commit)

    file_info = extract_repo_file_information(
        full_filename=os.path.join(commit_worktree.directory, generator_definition.file_path.as_posix()),
        repo_directory=repository.directory_root,
        worktree_directory=commit_worktree.directory,
    )
    generator_instance = await _define_instance(message=message, service=service)

    try:
        generator_class = generator_definition.load_class(
            import_root=repository.directory_root, relative_path=file_info.relative_repo_path_dir
        )

        generator = generator_class(
            query=generator_definition.query,
            client=service.client,
            branch=message.branch_name,
            params=message.variables,
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


async def _define_instance(message: messages.RequestGeneratorRun, service: InfrahubServices) -> InfrahubNode:
    if message.generator_instance:
        instance = await service.client.get(
            kind=InfrahubKind.GENERATORINSTANCE, id=message.generator_instance, branch=message.branch_name
        )
        instance.status.value = GeneratorInstanceStatus.PENDING.value
        await instance.update(do_full_update=True)

    else:
        async with lock.registry.get(
            f"{message.target_id}-{message.generator_definition.definition_id}", namespace="generator"
        ):
            instances = await service.client.filters(
                kind=InfrahubKind.GENERATORINSTANCE,
                definition__ids=[message.generator_definition.definition_id],
                object__ids=[message.target_id],
                branch=message.branch_name,
            )
            if instances:
                instance = instances[0]
                instance.status.value = GeneratorInstanceStatus.PENDING.value
                await instance.update(do_full_update=True)
            else:
                instance = await service.client.create(
                    kind=InfrahubKind.GENERATORINSTANCE,
                    branch=message.branch_name,
                    data={
                        "name": f"{message.generator_definition.definition_name}: {message.target_name}",
                        "status": GeneratorInstanceStatus.PENDING.value,
                        "object": message.target_id,
                        "definition": message.generator_definition.definition_id,
                    },
                )
                await instance.save()
    return instance
