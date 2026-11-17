import re
import sys

import typer
from infrahub_sdk import InfrahubClientSync

from infrahub import config
from infrahub.core.constants import InfrahubKind
from infrahub.git_credential.client import build_client_config

app = typer.Typer()

REGEX_USERNAME = r"^Username.*\'(.*)\'"
REGEX_PASSWORD = r"^Password.*\'(.*\:\/\/)(.*)@(.*)\'"


@app.command()
def askpass(
    text: list[str] | None = typer.Argument(None),
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    config.SETTINGS.initialize_and_exit(config_file=config_file)

    text = text or sys.stdin.read().strip()
    request_type = None

    if isinstance(text, list):
        text = " ".join(text)

    if re.match(pattern=REGEX_USERNAME, string=text):
        location = re.search(REGEX_USERNAME, text).group(1)
        request_type = "username"
    elif re.match(pattern=REGEX_PASSWORD, string=text):
        location = f"{re.search(REGEX_PASSWORD, text).group(1)}{re.search(REGEX_PASSWORD, text).group(3)}"
        request_type = "password"

    if not request_type:
        raise typer.Exit(f"Unable to identify the request type in '{text}'")

    client = InfrahubClientSync(config=build_client_config())
    repo = client.get(kind=InfrahubKind.GENERICREPOSITORY, location__value=location)

    if not repo.credential._id:
        raise typer.Exit("Repository doesn't have credentials defined.")

    repo.credential.fetch()

    attr = getattr(repo.credential.peer, request_type)
    print(attr.value)
