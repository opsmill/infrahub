from infrahub_sdk.exceptions import ModuleImportError
from infrahub_sdk.node import InfrahubNode
from infrahub_sdk.schema.repository import InfrahubGeneratorDefinitionConfig
from prefect import flow
from prefect.logging import get_run_logger

from infrahub import lock
from infrahub.core.constants import GeneratorInstanceStatus, InfrahubKind, ValidatorConclusion
from infrahub.core.timestamp import Timestamp
from infrahub.git.base import extract_repo_file_information
from infrahub.git.repository import get_initialized_repo
from infrahub.message_bus import messages
from infrahub.services import InfrahubServices
from infrahub.tasks.check import set_check_status
from infrahub.workflows.utils import add_tags


@flow(
    name="git-repository-check-generator-run",
    flow_run_name="Execute Generator {message.generator_definition.definition_name} for {message.target_name}",
)
async def run(message: messages.CheckGeneratorRun, service: InfrahubServices) -> None:
    if message.proposed_change:
        await add_tags(branches=[message.branch_name], nodes=[message.proposed_change], db_change=True)
    else:
        await add_tags(branches=[message.branch_name], nodes=[message.repository_id], db_change=True)

    log = get_run_logger()

    repository = await get_initialized_repo(
        repository_id=message.repository_id,
        name=message.repository_name,
        service=service,
        repository_kind=message.repository_kind,
        commit=message.commit,
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
        full_filename=commit_worktree.directory / generator_definition.file_path,
        repo_directory=repository.directory_root,
        worktree_directory=commit_worktree.directory,
    )
    generator_instance = await _define_instance(message=message, service=service)

    check_message = "Instance successfully generated"
    try:
        log.debug(f"repo information {file_info}")
        log.debug(f"Root directory : {repository.directory_root}")
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
        generator._init_client.request_context = message.context.to_request_context()
        await generator.run(identifier=generator_definition.name)
        generator_instance.status.value = GeneratorInstanceStatus.READY.value
    except ModuleImportError as exc:
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to import generator: {exc.message}"
        log.exception(check_message, exc_info=exc)
    except Exception as exc:
        conclusion = ValidatorConclusion.FAILURE
        generator_instance.status.value = GeneratorInstanceStatus.ERROR.value
        check_message = f"Failed to execute generator: {str(exc)}"
        log.exception(check_message, exc_info=exc)

    log.info("Generator run completed, starting update")
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
