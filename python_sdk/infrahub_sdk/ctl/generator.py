from pathlib import Path
from typing import Optional

from rich.console import Console

from infrahub_sdk import InfrahubNode
from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.repository import get_repository_config
from infrahub_sdk.ctl.utils import execute_graphql_query, parse_cli_vars
from infrahub_sdk.schema import InfrahubRepositoryConfig


async def run(
    generator_name: str,
    path: str,
    debug: bool,
    list_available: bool,
    branch: Optional[str] = None,
    variables: Optional[list[str]] = None,
):  # pylint: disable=unused-argument
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    if list_available:
        list_generators(repository_config=repository_config)
        return

    matched = [generator for generator in repository_config.generator_definitions if generator.name == generator_name]  # pylint: disable=not-an-iterable

    console = Console()

    if not matched:
        console.print(f"[red]Unable to find requested generator: {generator_name}")
        list_generators(repository_config=repository_config)
        return

    generator_config = matched[0]
    generator_class = generator_config.load_class()
    variables_dict = parse_cli_vars(variables)

    param_key = list(generator_config.parameters.keys())
    identifier = None
    if param_key:
        identifier = param_key[0]

    client = await initialize_client()
    if variables_dict:
        data = execute_graphql_query(
            query=generator_config.query,
            variables_dict=variables_dict,
            branch=branch,
            debug=False,
            repository_config=repository_config,
        )
        generator = generator_class(
            query=generator_config.query,
            client=client,
            branch=branch,
            params=variables_dict,
            convert_query_response=generator_config.convert_query_response,
            infrahub_node=InfrahubNode,
        )
        await generator._init_client.schema.all(branch=generator.branch_name)
        await generator.process_nodes(data=data)
        await generator.run(identifier=generator_config.name, data=data)

    else:
        targets = await client.get(
            kind="CoreGroup", branch=branch, include=["members"], name__value=generator_config.targets
        )
        await targets.members.fetch()
        for member in targets.members.peers:
            check_parameter = {}
            if identifier:
                attribute = getattr(member.peer, identifier)
                check_parameter = {identifier: attribute.value}
            params = {"name": member.peer.name.value}
            generator = generator_class(
                query=generator_config.query,
                client=client,
                branch=branch,
                params=params,
                convert_query_response=generator_config.convert_query_response,
                infrahub_node=InfrahubNode,
            )
            data = execute_graphql_query(
                query=generator_config.query,
                variables_dict=check_parameter,
                branch=branch,
                debug=False,
                repository_config=repository_config,
            )
            await generator._init_client.schema.all(branch=generator.branch_name)
            await generator.run(identifier=generator_config.name, data=data)


def list_generators(repository_config: InfrahubRepositoryConfig) -> None:
    console = Console()
    console.print(f"Generators defined in repository: {len(repository_config.generator_definitions)}")

    for generator in repository_config.generator_definitions:
        console.print(f"{generator.name} ({generator.file_path}::{generator.class_name}) Target: {generator.targets}")
