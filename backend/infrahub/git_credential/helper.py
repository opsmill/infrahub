import logging
import sys

import typer
from infrahub_sdk import Config, InfrahubClientSync
from infrahub_sdk.protocols import CoreGenericRepository

from infrahub import config

logging.getLogger("httpx").setLevel(logging.ERROR)
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
    """Return credentials for a repository if known, or exit cleanly.

    Per git's credential helper protocol, a helper MUST exit 0 when it has no
    credentials to offer (git then falls back to anonymous or the next
    helper). Exiting non-zero surfaces the helper's stderr to the caller as a
    git error, which is only appropriate for genuine failures (e.g. the
    request format isn't something we understand).
    """
    config.SETTINGS.initialize_and_exit(config_file=config_file)

    try:
        location = parse_helper_get_input(text=input_str)
    except ValueError as exc:
        # Malformed input from git — this is a real error.
        print(str(exc), file=sys.stderr)
        raise typer.Exit(1) from exc

    client = InfrahubClientSync(config=Config(address=config.SETTINGS.main.internal_address, insert_tracker=True))
    repo = client.get(
        kind=CoreGenericRepository.__name__,
        location__value=location,
        raise_when_missing=False,
    )

    # "No credentials available" is not an error to git. Exit 0 silently so it
    # can try the request anonymously (matters for public repos and during
    # check_connectivity before the repo is persisted).
    if repo is None:
        raise typer.Exit(0)
    if not repo.credential._id:
        raise typer.Exit(0)

    repo.credential.fetch()

    print(f"username={repo.credential.peer.username.value}")
    print(f"password={repo.credential.peer.password.value}")


@app.command()
def store(
    input_str: str = typer.Argument(None),  # noqa: ARG001
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),  # noqa: ARG001
) -> None:
    raise typer.Exit()
