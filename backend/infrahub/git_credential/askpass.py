import os
import re
import sys
from asyncio import run as aiorun
from typing import List, Optional

import typer

import infrahub.config as config
from infrahub_client import InfrahubClient

from .utils import QUERY

app = typer.Typer()

REGEX_USERNAME = r"^Username.*\'(.*)\'"
REGEX_PASSWORD = r"^Password.*\'(.*\:\/\/)(.*)@(.*)\'"


@app.command()
async def _askpass(text: Optional[List[str]] = typer.Argument(None)):
    text = text or sys.stdin.read().strip()
    request_type = None

    if isinstance(text, list):
        text = " ".join(text)

    if re.match(pattern=REGEX_USERNAME, string=text):
        location = re.search(REGEX_USERNAME, text).group(1)
        request_type = "username"
    elif re.match(pattern=REGEX_PASSWORD, string=text):
        location = f"{re.search(REGEX_USERNAME, text).group(1)}{re.search(REGEX_USERNAME, text).group(3)}"
        request_type = "password"

    if not request_type:
        sys.exit(1)

    config.load_and_exit(config_file_name=os.environ.get("INFRAHUB_CONFIG", "infrahub.toml"))

    client = await InfrahubClient.init(address=config.SETTINGS.main.internal_address)
    response = await client.execute_graphql(query=QUERY, variables={"repository_location": location})

    print(response["repository"][request_type])


@app.command()
def askpass(text: Optional[List[str]] = typer.Argument(None)):
    aiorun(_askpass(text=text))
