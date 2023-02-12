import sys
from asyncio import run as aiorun

import typer

import infrahub.config as config
from infrahub_client import InfrahubClient

from .utils import QUERY

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
    elif "path" not in input_dict:
        raise ValueError(
            """Git usehttppath must be enabled to use this helper. You can active it with
    git config --global credential.usehttppath true
    """
        )

    return f"{input_dict['protocol']}://{input_dict['host']}/{input_dict['path']}"


async def _get(input: str, config_file: str):
    config.load_and_exit(config_file_name=config_file)

    try:
        location = parse_helper_get_input(text=input)
    except ValueError as exc:
        sys.exit(str(exc))

    # FIXME currently we are only querying the repo in the main branch,
    # this will not work if a new repository is added in a branch first.
    client = await InfrahubClient.init(address=config.SETTINGS.main.internal_address)
    response = await client.execute_graphql(query=QUERY, variables={"repository_location": location})

    if len(response["repository"]) == 0:
        sys.exit("Repository not found in the database.")

    print(f"username={response['repository'][0]['username']['value']}")
    print(f"password={response['repository'][0]['password']['value']}")


async def _store(
    input: str,
    config_file: str,
):
    sys.exit(0)


@app.command()
def get(
    input: str = typer.Argument(... if sys.stdin.isatty() else sys.stdin.read().strip()),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):
    aiorun(_get(input=input, config_file=config_file))


@app.command()
def store(
    input: str = typer.Argument(None),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):
    aiorun(_store(input=input, config_file=config_file))
