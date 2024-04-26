import os

from infrahub_sdk import InfrahubNode
from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.schema import InfrahubGeneratorDefinitionConfig

from infrahub import lock
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.repository import extract_repo_file_information, get_initialized_repo
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.check import set_check_status

# pylint: disable=duplicate-code


async def run(message: messages.CheckGeneratorRun, service: InfrahubServices):
    repository = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
    )

    conclusion = ValidatorConclusion.SUCCESS

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

    check_message = "Instance successfully generated"
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
    except ModuleImportError as exc:
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to import generator: {exc.message}"
    except Exception as exc:  # pylint: disable=broad-exception-caught
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to execute generator: {str(exc)}"

    await generator_instance.update(do_full_update=True)

    check = None
    existing_check = await service.client.filters(
        kind=InfrahubKind.GENERATORCHECK, validator__ids=message.validator_id, instance__value=generator_instance.id
    )
    if existing_check:
        check = existing_check[0]

    if check:
        check.created_at.value = Timestamp().to_string()
        check.conclusion.value = conclusion.value
        await check.save()
    else:
        check = await service.client.create(
            kind=InfrahubKind.GENERATORCHECK,
            data={
                "name": message.target_name,
                "origin": message.repository_id,
                "kind": "GeneratorDefinition",
                "validator": message.validator_id,
                "created_at": Timestamp().to_string(),
                "message": check_message,
                "conclusion": conclusion.value,
                "instance": generator_instance.id,
            },
        )
        await check.save()

    await set_check_status(message=message, conclusion=conclusion.value, service=service)


async def _define_instance(message: messages.CheckGeneratorRun, service: InfrahubServices) -> InfrahubNode:
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
