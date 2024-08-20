import importlib
import logging
import sys
from asyncio import run as aiorun
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Optional

import typer
from rich.console import Console
from rich.logging import RichHandler

from infrahub_sdk import InfrahubClient
from infrahub_sdk.checks import InfrahubCheck
from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.exceptions import QueryNotFoundError
from infrahub_sdk.ctl.repository import get_repository_config
from infrahub_sdk.ctl.utils import catch_exception, execute_graphql_query
from infrahub_sdk.schema import InfrahubCheckDefinitionConfig, InfrahubRepositoryConfig

app = typer.Typer()
console = Console()


@dataclass
class CheckModule:
    name: str
    module: ModuleType
    definition: InfrahubCheckDefinitionConfig

    def get_check(self) -> InfrahubCheck:
        return getattr(self.module, self.definition.class_name)


@app.callback()
def callback() -> None:
    """
    Execute user-defined checks.
    """


@app.command()
@catch_exception(console=console)
def run(
    *,
    path: str,
    debug: bool,
    format_json: bool,
    list_available: bool,
    variables: dict[str, str],
    name: Optional[str] = None,
    branch: Optional[str] = None,
) -> None:
    """Locate and execute all checks under the defined path."""

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))

    if list_available:
        list_checks(repository_config=repository_config)
        return

    check_definitions = repository_config.check_definitions
    if name:
        check_definitions = [check for check in repository_config.check_definitions if check.name == name]  # pylint: disable=not-an-iterable
        if not check_definitions:
            console.print(f"[red]Unable to find requested transform: {name}")
            list_checks(repository_config=repository_config)
            return

    check_modules = get_modules(check_definitions=check_definitions)
    aiorun(
        run_checks(
            check_modules=check_modules,
            format_json=format_json,
            path=path,
            variables=variables,
            branch=branch,
            repository_config=repository_config,
        )
    )


async def run_check(
    check_module: CheckModule,
    client: InfrahubClient,
    format_json: bool,
    path: str,
    repository_config: InfrahubRepositoryConfig,
    branch: Optional[str] = None,
    params: Optional[dict] = None,
) -> bool:
    module_name = check_module.name
    output = "stdout" if format_json else None
    log = logging.getLogger("infrahub")
    passed = True
    check_class = check_module.get_check()
    check = await check_class.init(client=client, params=params, output=output, root_directory=path, branch=branch)
    param_log = f" - {params}" if params else ""
    try:
        data = execute_graphql_query(
            query=check.query,
            variables_dict=check.params,
            repository_config=repository_config,
            branch=branch,
            debug=False,
        )
        passed = await check.run(data)
        if passed:
            if not format_json:
                log.info(f"{module_name}::{check}: [green]PASSED[/]{param_log}", extra={"markup": True})
        else:
            passed = False
            if not format_json:
                log.error(f"{module_name}::{check}: [red]FAILED[/]{param_log}", extra={"markup": True})

                for log_message in check.logs:
                    log.error(f"  {log_message['message']}")

    except QueryNotFoundError as exc:
        log.warning(f"{module_name}::{check}: unable to find query ({str(exc)})")
        passed = False
    except Exception as exc:  # pylint: disable=broad-exception-caught
        log.warning(f"{module_name}::{check}: An error occurred during execution ({exc})")
        passed = False

    return passed


async def run_targeted_check(
    check_module: CheckModule,
    client: InfrahubClient,
    format_json: bool,
    path: str,
    repository_config: InfrahubRepositoryConfig,
    variables: dict[str, str],
    branch: Optional[str] = None,
) -> bool:
    filters = {}
    param_value = list(check_module.definition.parameters.values())
    if param_value:
        filters[param_value[0]] = check_module.definition.targets

    param_key = list(check_module.definition.parameters.keys())
    identifier = None
    if param_key:
        identifier = param_key[0]

    check_summary: list[bool] = []
    if variables:
        result = await run_check(
            check_module=check_module,
            client=client,
            format_json=format_json,
            path=path,
            branch=branch,
            params=variables,
            repository_config=repository_config,
        )
        check_summary.append(result)
    else:
        targets = await client.get(kind="CoreGroup", include=["members"], **filters)
        await targets.members.fetch()
        for member in targets.members.peers:
            check_parameter = {}
            if identifier:
                attribute = getattr(member.peer, identifier)
                check_parameter = {identifier: attribute.value}
            result = await run_check(
                check_module=check_module,
                client=client,
                format_json=format_json,
                path=path,
                branch=branch,
                params=check_parameter,
                repository_config=repository_config,
            )
            check_summary.append(result)

    return all(check_summary)


async def run_checks(
    check_modules: list[CheckModule],
    format_json: bool,
    path: str,
    variables: dict[str, str],
    repository_config: InfrahubRepositoryConfig,
    branch: Optional[str] = None,
) -> None:
    log = logging.getLogger("infrahub")

    check_summary: list[bool] = []
    client = await initialize_client()
    for check_module in check_modules:
        if check_module.definition.targets:
            result = await run_targeted_check(
                check_module=check_module,
                client=client,
                repository_config=repository_config,
                format_json=format_json,
                path=path,
                variables=variables,
                branch=branch,
            )
            check_summary.append(result)
        else:
            result = await run_check(
                check_module=check_module,
                client=client,
                format_json=format_json,
                path=path,
                branch=branch,
                repository_config=repository_config,
            )
            check_summary.append(result)

    if not check_modules:
        if not format_json:
            log.warning("No check found")
        else:
            print('{"level": "WARNING", "message": "message", ""No check found"}')

    if not all(check_summary):
        sys.exit(1)


def get_modules(check_definitions: list[InfrahubCheckDefinitionConfig]) -> list[CheckModule]:
    log = logging.getLogger("infrahub")
    modules = []
    for check_definition in check_definitions:
        directory_name = str(check_definition.file_path.parent)
        module_name = check_definition.file_path.stem

        if directory_name not in sys.path:
            sys.path.append(directory_name)

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            log.error(f"Unable to load {check_definition.file_path}")
            continue

        if check_definition.class_name not in dir(module):
            log.error(f"{check_definition.class_name} class not found in {check_definition.file_path}")
            continue
        modules.append(CheckModule(name=module_name, module=module, definition=check_definition))

    return modules


def list_checks(repository_config: InfrahubRepositoryConfig) -> None:
    console.print(f"Python checks defined in repository: {len(repository_config.check_definitions)}")

    for check in repository_config.check_definitions:
        target = check.targets or "-global-"
        console.print(f"{check.name} ({check.file_path}::{check.class_name}) Target: {target}")
