from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from infrahub_sdk.graphql import Mutation
from infrahub_sdk.protocols import CoreGeneratorDefinition, CoreGeneratorInstance, CoreStandardGroup
from prefect.client.orchestration import get_client
from prefect.client.schemas.filters import FlowFilter, FlowFilterName, FlowRunFilter, FlowRunFilterTags

from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.initialization import create_ipam_namespace
from infrahub.workflows.constants import WorkflowTag
from tests.helpers.file_repo import FileRepo

if TYPE_CHECKING:
    from pathlib import Path

    from infrahub_sdk import InfrahubClient
    from infrahub_sdk.node import InfrahubNode

    from infrahub.database import InfrahubDatabase

REPOSITORY_NAME = "dedicated-internet"
SERVICE_KIND = "ServiceDedicatedInternet"
ALLOCATE_GENERATOR = "dedicated_internet_allocate"
ACTIVATE_GENERATOR = "dedicated_internet_activate"
ALLOCATE_TARGETS = "dedicated_internet_allocate_targets"
ACTIVATE_TARGETS = "dedicated_internet_activate_targets"


@pytest.fixture(scope="class")
async def dedicated_internet_repo(
    db: InfrahubDatabase,
    initialize_registry: None,
    client: InfrahubClient,
    git_repos_source_dir_module_scope: Path,
    git_repos_dir_module_scope: Path,
    prefect_test_fixture: None,
) -> InfrahubNode:
    """Import the dedicated-internet fixture repository on main.

    Loads its schema, supporting objects and pools, both target groups, both queries and both generator definitions.
    """
    # The repository's IP pools resolve the default namespace, which a fresh test database lacks.
    namespace = await create_ipam_namespace(db=db)
    registry.default_ipnamespace = namespace.id

    FileRepo(name=REPOSITORY_NAME, sources_directory=git_repos_source_dir_module_scope)
    repository = await client.create(
        kind=InfrahubKind.REPOSITORY,
        data={"name": REPOSITORY_NAME, "location": f"{git_repos_source_dir_module_scope}/{REPOSITORY_NAME}"},
    )
    await repository.save()
    return repository


async def create_service(
    client: InfrahubClient, branch: str, name: str, location: str = "site-a", **data: Any
) -> InfrahubNode:
    service = await client.create(
        kind=SERVICE_KIND,
        branch=branch,
        data={"name": name, "location": [location], "bandwidth": "1000", "ip_package": "small", **data},
    )
    await service.save()
    return service


async def add_to_group(client: InfrahubClient, branch: str, group_name: str, node_id: str) -> None:
    group = await client.get(kind=CoreStandardGroup, name__value=group_name, branch=branch)
    await group.add_relationships(relation_to_update="members", related_nodes=[node_id])


async def run_generator(client: InfrahubClient, branch: str, definition_name: str, node_id: str) -> None:
    """Run one generator definition for one target on a branch and wait for it.

    A failing generator raises GraphQLError("generator run failures"); see `failed_run_messages` for its cause.
    """
    definition = await client.get(kind=CoreGeneratorDefinition, name__value=definition_name, branch=branch)
    mutation = Mutation(
        mutation="CoreGeneratorDefinitionRun",
        input_data={"data": {"id": definition.id, "nodes": [node_id]}, "wait_until_completion": True},
        query={"ok": None},
    )
    await client.execute_graphql(query=mutation.render(), branch_name=branch)


async def get_generator_instance(
    client: InfrahubClient, branch: str, definition_name: str, node_id: str
) -> CoreGeneratorInstance:
    definition = await client.get(kind=CoreGeneratorDefinition, name__value=definition_name, branch=branch)
    return await client.get(
        kind=CoreGeneratorInstance, definition__ids=[definition.id], object__ids=[node_id], branch=branch
    )


async def failed_run_messages(instance_id: str) -> list[str]:
    """State messages of the failed runs of a generator instance.

    The run mutation only reports "generator run failures"; the generator's own exception lives on its flow run.
    """
    async with get_client(sync_client=False) as prefect:
        runs = await prefect.read_flow_runs(
            flow_filter=FlowFilter(name=FlowFilterName(any_=["generator-run"])),
            flow_run_filter=FlowRunFilter(
                tags=FlowRunFilterTags(all_=[WorkflowTag.RELATED_NODE.render(identifier=instance_id)])
            ),
        )
    return [run.state.message or "" for run in runs if run.state and run.state.is_failed()]


async def service_port_ids(client: InfrahubClient, branch: str, service_id: str) -> list[str]:
    return [port.id for port in await client.filters(kind="DcimInterface", service__ids=[service_id], branch=branch)]


async def port_id(client: InfrahubClient, branch: str, device: str, name: str) -> str:
    return (await client.get(kind="DcimInterface", hfid=[device, name], branch=branch)).id
