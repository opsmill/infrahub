import glob
import importlib
import logging
import os
import sys
from typing import Optional

import typer
from rich.logging import RichHandler

app = typer.Typer()


INFRAHUB_CHECK_VARIABLE_TO_IMPORT = "INFRAHUB_CHECKS"


# pylint: disable=too-many-nested-blocks,too-many-branches


@app.callback()
def callback() -> None:
    """
    Execute user-defined checks.
    """


@app.command()
def run(
    branch: Optional[str] = None,
    path: Optional[str] = typer.Argument("."),
    rebase: bool = True,
    debug: bool = False,
    format_json: bool = False,
) -> None:
    """Locate and execute all checks under the defined path."""

    log_level = "DEBUG" if debug else "INFO"

    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahub")

    python_files = glob.glob(f"{path}/**/*.py", recursive=True)

    passed_checks = []
    failed_checks = []

    nbr_checks_found = 0

    # search for python file
    for python_file in python_files:
        directory_name = os.path.dirname(python_file)
        filename = os.path.basename(python_file)
        module_name = os.path.splitext(filename)[0]

        if directory_name not in sys.path:
            sys.path.append(directory_name)

        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue

        if INFRAHUB_CHECK_VARIABLE_TO_IMPORT not in dir(module):
            continue

        for check_class in getattr(module, INFRAHUB_CHECK_VARIABLE_TO_IMPORT):
            nbr_checks_found += 1
            try:
                output = "stdout" if format_json else None
                check = check_class(output=output, root_directory=path, branch=branch, rebase=rebase)
                passed = check.run()

                if passed:
                    if not format_json:
                        log.info(f"{module_name}: [green]PASSED[/]", extra={"markup": True})
                    passed_checks.append(module_name)
                else:
                    failed_checks.append(module_name)
                    if not format_json:
                        log.error(f"{module_name}: [red]FAILED[/]", extra={"markup": True})

                        for log_message in check.logs:
                            log.error(f"  {log_message['message']}")

            except Exception as exc:  # pylint: disable=broad-except
                log.warning(f"{module_name}: An error occured during execution ({exc})")

    if nbr_checks_found == 0:
        if not format_json:
            log.warning("No check found")
        else:
            print('{"level": "WARNING", "message": "message", ""No check found"}')

    if failed_checks or not passed_checks:
        sys.exit(1)
