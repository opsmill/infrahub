import sys

import typer
from infrahub_sdk import Config, InfrahubClientSync

from infrahub import config
from infrahub.core.constants import InfrahubKind

app = typer.Typer()


def parse_helper_get_input(text: str) -> str:
    """Parse the input provided to infrahub-githelper get

    Format1 (with usehttppath true)
      protocol=https
      host=github.com
      path=opsmill/infrahub-demo-edge.git

    Format2 (without usehttppath true)(default)
      protocol=https
      host=github.com
    """
    input_dict = {line.split("=")[0]: line.split("=")[1] for line in text.splitlines() if "=" in line}

    if "protocol" not in input_dict or "host" not in input_dict:
        raise ValueError("Input format not supported.")
    if "path" not in input_dict:
        raise ValueError(
            """Git usehttppath must be enabled to use this helper. You can active it with
    git config --global credential.usehttppath true
    """
        )

    return f"{input_dict['protocol']}://{input_dict['host']}/{input_dict['path']}"


@app.command()
def get(
    input_str: str = typer.Argument(... if sys.stdin.isatty() else sys.stdin.read().strip()),
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    config.SETTINGS.initialize_and_exit(config_file=config_file)

    try:
        location = parse_helper_get_input(text=input_str)
    except ValueError as exc:
        print(str(exc))
        raise typer.Exit(1) from exc

    # FIXME currently we are only querying the repo in the main branch,
    # this will not work if a new repository is added in a branch first.
    client = InfrahubClientSync.init(config=Config(address=config.SETTINGS.main.internal_address, insert_tracker=True))
    repo = client.get(kind=InfrahubKind.GENERICREPOSITORY, location__value=location)

    if not repo:
        print("Repository not found in the database.")
        raise typer.Exit(1)

    print(f"username={repo.username.value}")
    print(f"password={repo.password.value}")


# pylint: disable=unused-argument
@app.command()
def store(
    input_str: str = typer.Argument(None),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    raise typer.Exit()
