import logging
from asyncio import run as aiorun
from pathlib import Path

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console
from rich.logging import RichHandler

import infrahub_ctl.config as config
from infrahub_client import InfrahubClient

app = typer.Typer()


@app.callback()
def callback():
    """
    Manage the schema in a remote Infrahub instance.
    """


async def _load(schema: Path, log: logging.Logger):
    console = Console()

    try:
        schema_data = yaml.safe_load(schema.read_text())
    except yaml.YAMLError as exc:
        console.print("[red]Invalid JSON file")
        raise typer.Exit(2) from exc

    client = await InfrahubClient.init(address=config.SETTINGS.server_address, insert_tracker=True)

    try:
        client.schema.validate(schema_data)
    except ValidationError as exc:
        console.print(f"[red]Schema not valid, found '{len(exc.errors())}' error(s)")
        for error in exc.errors():
            loc_str = [str(item) for item in error["loc"]]
            console.print(f"  '{'/'.join(loc_str)}' | {error['msg']} ({error['type']})")
        raise typer.Exit(2)

    current_nodes = {item.kind.value: item for item in await client.all(kind="NodeSchema")}
    # current_generics = {item.kind.value: item for item in await client.all(kind="GenericSchema")}

    # Nodes
    for node in schema_data.get("nodes"):
        if node["kind"] in current_nodes:
            # Ignoring the existing nodes for now, will need to revisit
            pass

        node_data = {key: value for key, value in node.items() if key not in ["relationships", "attributes"]}
        log.info(f"Loading schema for : {node_data['kind']}")
        new_node = await client.create(kind="NodeSchema", data=node_data)
        await new_node.save()

        for attribute in node.get("attributes", []):
            attribute["node"] = str(new_node.id)
            new_attribute = await client.create(kind="AttributeSchema", data=attribute)
            await new_attribute.save()
            log.debug(f"  - Attribute {attribute['name']}")

        for rel in node.get("relationships", []):
            rel["node"] = str(new_node.id)
            new_rel = await client.create(kind="RelationshipSchema", data=rel)
            await new_rel.save()
            log.debug(f"  - Relationship {rel['name']}")

    # Node Extensions
    for node in schema_data.get("node_extensions"):
        if node["kind"] not in current_nodes:
            # Ignoring the existing nodes for now, will need to revisit
            pass

        node_data = {key: value for key, value in node.items() if key not in ["relationships", "attributes"]}
        log.info(f"Loading schema for : {node_data['kind']}")
        new_node = await client.create(kind="NodeSchema", data=node_data)
        await new_node.save()

        for attribute in node.get("attributes", []):
            attribute["node"] = str(new_node.id)
            new_attribute = await client.create(kind="AttributeSchema", data=attribute)
            await new_attribute.save()
            log.debug(f"  - Attribute {attribute['name']}")

        for rel in node.get("relationships", []):
            rel["node"] = str(new_node.id)
            new_rel = await client.create(kind="RelationshipSchema", data=rel)
            await new_rel.save()
            log.debug(f"  - Relationship {rel['name']}")


@app.command()
def load(
    schema: Path,
    debug: bool = False,
    config_file: str = typer.Option("infrahubctl.toml", envvar="INFRAHUBCTL_CONFIG"),
):
    """Load a schema file into Infrahub."""
    config.load_and_exit(config_file=config_file)

    logging.getLogger("infrahub_client").setLevel(logging.CRITICAL)

    log_level = "DEBUG" if debug else "INFO"
    FORMAT = "%(message)s"
    logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
    log = logging.getLogger("infrahubctl")

    aiorun(_load(schema=schema, log=log))


@app.command()
def migrate():
    """Migrate the schema to the latest version. (Not Implemented Yet)"""
    print("Not implemented yet.")
