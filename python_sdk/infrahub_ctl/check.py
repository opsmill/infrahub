import importlib
import logging
import os
import sys
from asyncio import run as aiorun
from pathlib import Path
from types import ModuleType
from typing import List, Optional, TypedDict

import typer
from rich.logging import RichHandler

from infrahub_ctl import config
from infrahub_ctl.client import initialize_client
from infrahub_ctl.repository import get_repository_config
from infrahub_sdk import InfrahubClient
from infrahub_sdk.schema import InfrahubCheckDefinitionConfig

app = typer.Typer()


INFRAHUB_CHECK_VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


class CheckModule(TypedDict):
    name: str
    module: ModuleType


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
    check_file: Optional[str] = None,
) -> None:
    """Locate and execute all checks under the defined path."""

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])

    if not config.SETTINGS:
        config.load_and_exit(config_file=config_file)

    check_definitions = get_available_checks(check_file=check_file)
    check_modules = get_modules(check_definitions=check_definitions)
    aiorun(run_checks(check_modules=check_modules, format_json=format_json, path=path, branch=branch))


async def run_check(
    check_module: CheckModule, client: InfrahubClient, format_json: bool, path: str, branch: Optional[str] = None
) -> bool:
    module_name = check_module["name"]
    module = check_module["module"]
    output = "stdout" if format_json else None
    log = logging.getLogger("infrahub")
    passed = True
    for check_class in getattr(module, INFRAHUB_CHECK_VARIABLE_TO_IMPORT):
        check = await check_class.init(client=client, output=output, root_directory=path, branch=branch)
        try:
            passed = await check.run()

            if passed:
                if not format_json:
                    log.info(f"{module_name}::{check}: [green]PASSED[/]", extra={"markup": True})
            else:
                passed = False
                if not format_json:
                    log.error(f"{module_name}::{check}: [red]FAILED[/]", extra={"markup": True})

                    for log_message in check.logs:
                        log.error(f"  {log_message['message']}")

        except Exception as exc:  # pylint: disable=broad-except
            log.warning(f"{module_name}::{check}: An error occured during execution ({exc})")
            passed = False
    return passed


async def run_checks(
    check_modules: List[CheckModule], format_json: bool, path: str, branch: Optional[str] = None
) -> None:
    log = logging.getLogger("infrahub")

    check_summary: List[bool] = []
    client = await initialize_client()
    for check_module in check_modules:
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

        if INFRAHUB_CHECK_VARIABLE_TO_IMPORT not in dir(module):
            log.error(f"{INFRAHUB_CHECK_VARIABLE_TO_IMPORT} variable not find in {check_definition.file_path}")
            continue
        modules.append({"name": module_name, "module": module})

    return modules


def get_available_checks(check_file: Optional[str] = None) -> List[InfrahubCheckDefinitionConfig]:
    repository_config = get_repository_config(Path(config.INFRAHUB_REPO_CONFIG_FILE))
    log = logging.getLogger("infrahub")
    if check_file:
        matched = [
            check_definition
            for check_definition in repository_config.check_definitions
            if check_definition.file_path == check_file
        ]
        if matched:
            return matched

        log.error(f"Unable to find check definition for {check_file} in .infrahub.yml")
        sys.exit(1)

    return repository_config.check_definitions
