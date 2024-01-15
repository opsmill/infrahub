import re
import sys
from typing import List, Optional

import typer
from infrahub_sdk import InfrahubClientSync

import infrahub.config as config
from infrahub.core.constants import InfrahubKind

app = typer.Typer()

REGEX_USERNAME = r"^Username.*\'(.*)\'"
REGEX_PASSWORD = r"^Password.*\'(.*\:\/\/)(.*)@(.*)\'"


@app.command()
def askpass(
    text: Optional[List[str]] = typer.Argument(None),
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
):
    if not config.SETTINGS:
        config.load_and_exit(config_file_name=config_file)

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

    client = InfrahubClientSync.init(address=config.SETTINGS.main.internal_address, insert_tracker=True)
    repo = client.get(kind=InfrahubKind.REPOSITORY, location__value=location)

    attr = getattr(repo, request_type)
    print(attr.value)
