import importlib
import logging
import os
import sys
from asyncio import run as aiorun
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, List, Optional

import typer
from rich.logging import RichHandler

from infrahub_sdk import InfrahubClient
from infrahub_sdk.checks import InfrahubCheck
from infrahub_sdk.ctl import config
from infrahub_sdk.ctl.client import initialize_client
from infrahub_sdk.ctl.exceptions import QueryNotFoundError
from infrahub_sdk.ctl.repository import get_repository_config
from infrahub_sdk.ctl.utils import execute_graphql_query
from infrahub_sdk.schema import InfrahubCheckDefinitionConfig

app = typer.Typer()


INFRAHUB_CHECK_VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


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
def run(
    branch: Optional[str] = None,
    path: str = typer.Argument("."),
    debug: bool = False,
    format_json: bool = False,
    config_file: str = typer.Option(config.DEFAULT_CONFIG_FILE, envvar=config.ENVVAR_CONFIG_FILE),
    name: Optional[str] = None,
) -> None:
    """Locate and execute all checks under the defined path."""

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    check_definitions = get_available_checks(name=name)
    check_modules = get_modules(check_definitions=check_definitions)
    aiorun(run_checks(check_modules=check_modules, format_json=format_json, path=path, branch=branch))


async def run_check(
    check_module: CheckModule,
    client: InfrahubClient,
    format_json: bool,
    path: str,
    branch: Optional[str] = None,
    params: Optional[Dict] = None,
) -> bool:
    module_name = check_module.name
    output = "stdout" if format_json else None
    log = logging.getLogger("infrahub")
    passed = True
    check_class = check_module.get_check()
    check = await check_class.init(client=client, params=params, output=output, root_directory=path, branch=branch)
    param_log = f" - {params}" if params else ""
    try:
        check.data = {
            "data": execute_graphql_query(query=check.query, variables_dict=check.params, branch=branch, debug=False)
        }
        passed = await check.run()
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
        log.warning(f"{module_name}::{check}: An error occured during execution ({exc})")
        passed = False

    return passed


async def run_targeted_check(
    check_module: CheckModule, client: InfrahubClient, format_json: bool, path: str, branch: Optional[str] = None
) -> bool:
    filters = {}
    param_value = list(check_module.definition.parameters.values())
    if param_value:
        filters[param_value[0]] = check_module.definition.targets

    param_key = list(check_module.definition.parameters.keys())
    identifier = None
    if param_key:
        identifier = param_key[0]

    check_summary: List[bool] = []
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
        )
        check_summary.append(result)

    return all(check_summary)


async def run_checks(
    check_modules: List[CheckModule], format_json: bool, path: str, branch: Optional[str] = None
) -> None:
    log = logging.getLogger("infrahub")

    check_summary: List[bool] = []
    client = await initialize_client()
    for check_module in check_modules:
        if check_module.definition.targets:
            result = await run_targeted_check(
                check_module=check_module, client=client, format_json=format_json, path=path, branch=branch
            )
            check_summary.append(result)
        else:
            result = await run_check(
                check_module=check_module, client=client, format_json=format_json, path=path, branch=branch
            )
            check_summary.append(result)

    if not check_modules:
        if not format_json:
            log.warning("No check found")
        else:
            print('{"level": "WARNING", "message": "message", ""No check found"}')

    if not all(check_summary):
        sys.exit(1)


def get_modules(check_definitions: List[InfrahubCheckDefinitionConfig]) -> List[CheckModule]:
    log = logging.getLogger("infrahub")
    modules = []
    for check_definition in check_definitions:
        directory_name = os.path.dirname(check_definition.file_path)
        filename = os.path.basename(check_definition.file_path)
        module_name = os.path.splitext(filename)[0]

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


def get_available_checks(name: Optional[str] = None) -> List[InfrahubCheckDefinitionConfig]:
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))
    log = logging.getLogger("infrahub")
    if name:
        matched = [
            check_definition
            for check_definition in repository_config.check_definitions
            if check_definition.name == name
        ]
        if matched:
            return matched
        available_checks = [check_definition.name for check_definition in repository_config.check_definitions]
        log.error(f"Unable to find check definition for {name} in .infrahub.yml {available_checks}")
        sys.exit(1)

    return repository_config.check_definitions
