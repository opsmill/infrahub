import logging
from asyncio import run as aiorun

import typer
from infrahub_sync.infrahub.adapter import InfrahubAdapter
from infrahub_sync.netbox.adapter import NetboxAdapter

app = typer.Typer()


logging.basicConfig(level=logging.INFO)

INFRAHUB_URL = "http://localhost:8000"

NETBOX_URL = "https://demo.netbox.dev"
NETBOX_TOKEN = "1719c7d7b5174662c14766351820ce872777569b"


async def _diff():
    ifha = InfrahubAdapter(url=INFRAHUB_URL)
    await ifha.load()

    na = NetboxAdapter(url=NETBOX_URL, token=NETBOX_TOKEN)
    await na.load()

    mydiff = ifha.diff_from(na)

    print(mydiff.str())


async def _sync():
    ifha = InfrahubAdapter(url=INFRAHUB_URL)
    await ifha.load()

    na = NetboxAdapter(url=NETBOX_URL, token=NETBOX_TOKEN)
    await na.load()

    mydiff = ifha.diff_from(na)
    print(mydiff.str())

    await ifha.sync_from(na, diff=mydiff)


@app.command()
def diff():
    aiorun(_diff())


@app.command()
def sync():
    aiorun(_sync())
