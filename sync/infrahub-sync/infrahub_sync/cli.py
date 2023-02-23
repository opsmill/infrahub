import logging
from asyncio import run as aiorun
from typing import Optional

import typer
from infrahub_sync.infrahub.adapter import InfrahubAdapter
from infrahub_sync.netbox.adapter import NetboxAdapter

app = typer.Typer()


logging.basicConfig(level=logging.INFO)

INFRAHUB_URL = "https://localhost:8000"

NETBOX_URL = "https://demo.netbox.dev"
NETBOX_TOKEN = "d14fc45811bf34a2e843ed87023dcefd81b5cb3a"


async def _diff():
    iha = InfrahubAdapter(url=INFRAHUB_URL)
    await iha.load()

    na = NetboxAdapter(url=NETBOX_URL, token=NETBOX_TOKEN)
    await na.load()

    diff = iha.diff_from(na)

    print(diff.str())


@app.command()
def diff():
    aiorun(_diff())


@app.command()
def sync(name: Optional[str] = None):
    pass
