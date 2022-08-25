import sys
from typing import Optional

import typer

import infrahub.config as config

app = typer.Typer()

TEST_DATABASE = "infrahub.testing"


@app.command()
def unit(
    path: Optional[str] = typer.Argument(None),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
):

    if not path:
        path = "./tests/unit"

    config.load_and_exit(config_file_name=config_file)
    config.SETTINGS.database.database = TEST_DATABASE

    verbose_str = "-" + "v" * verbose if verbose else "-v"

    import pytest

    sys.exit(pytest.main([path, verbose_str]))


@app.command()
def integration(
    path: Optional[str] = typer.Argument(None),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
):

    if not path:
        path = "./tests/integration"

    config.load_and_exit(config_file_name=config_file)
    config.SETTINGS.database.database = TEST_DATABASE

    verbose_str = "-" + "v" * verbose if verbose else "-v"

    import pytest

    sys.exit(pytest.main(["-x", path, verbose_str]))


@app.command()
def all(
    path: Optional[str] = typer.Argument(None),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    verbose: int = typer.Option(0, "--verbose", "-v", count=True),
):

    if not path:
        path = "."

    config.load_and_exit(config_file_name=config_file)
    config.SETTINGS.database.database = TEST_DATABASE

    verbose_str = "-" + "v" * verbose if verbose else "-v"

    import pytest

    sys.exit(pytest.main([path, verbose_str]))
