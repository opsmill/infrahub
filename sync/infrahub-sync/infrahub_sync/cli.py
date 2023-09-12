import glob
import importlib
import logging
import os
from pathlib import Path
from typing import List, Optional
from diffsync.diff import Diff

import typer
import yaml
from infrahub_sync import SyncAdapter, SyncConfig, SyncInstance
from infrahub_sync.generator import render_template
from potenda import Potenda

from infrahub_client import InfrahubClientSync

app = typer.Typer()


logging.basicConfig(level=logging.WARNING)


def print_error_and_abort(message: str):
    error_message = typer.style(f"Error: {message}", fg=typer.colors.RED, bold=True)
    typer.echo(error_message)
    raise typer.Abort()

def import_adapter(adapter: SyncAdapter, directory: str):
    here = os.path.abspath(os.path.dirname(__file__))
    relative_directory = directory.replace(here, "")[1:]
    module = importlib.import_module(f"infrahub_sync.{relative_directory.replace('/', '.')}.{adapter.name}.adapter")
    return getattr(module, f"{adapter.name.title()}Sync")


def get_all_sync() -> List[SyncInstance]:
    results = []
    here = os.path.abspath(os.path.dirname(__file__))

    for config_file in glob.glob(f"{here}/sync/**/config.yml", recursive=True):
        directory_name = os.path.dirname(config_file)
        config_data = yaml.safe_load(Path(config_file).read_text())
        SyncConfig(**config_data)
        results.append(SyncInstance(**config_data, directory=directory_name))

    return results


def get_instance(name: str) -> Optional[SyncInstance]:
    for item in get_all_sync():
        if item.name == name:
            return item

    return None

def get_potenda_from_instance(sync_instance: SyncInstance, branch: Optional[str] = None) -> Potenda:
    source = import_adapter(adapter=sync_instance.source, directory=sync_instance.directory)
    destination = import_adapter(adapter=sync_instance.destination, directory=sync_instance.directory)

    if sync_instance.source.name == "infrahub" and branch:
        src = source(config=sync_instance, target="source", adapter=sync_instance.source, branch=branch)
    else:
        src = source(config=sync_instance, target="source", adapter=sync_instance.source)
    if sync_instance.destination.name == "infrahub" and branch:
        dst = destination(config=sync_instance, target="destination", adapter=sync_instance.destination, branch=branch)
    else:
        dst = destination(config=sync_instance, target="destination", adapter=sync_instance.destination)

    ptd = Potenda(destination=dst, source=src, config=sync_instance, top_level=sync_instance.order)

    return ptd


@app.command()
def list():
    """List all available SYNC projects."""
    for item in get_all_sync():
        typer.echo(f"{item.name} | {item.source.name} >> {item.destination.name} | {item.directory}")


@app.command()
def diff(
    name: str = typer.Argument(..., help="Name of the sync to use"),
    branch: str = typer.Option(default=None, help="Branch to use for the sync."),
):
    """Calculate and print the differences between the source and the destination systems for a given project."""
    sync_instance = get_instance(name=name)
    if not sync_instance:
        print_error_and_abort(f"Unable to find the sync {name}. Use the list command to see the sync available")

    ptd = get_potenda_from_instance(sync_instance, branch)
    ptd.load()
    
    mydiff = ptd.diff()
    
    print(mydiff.str())


@app.command()
def sync(
    name: str = typer.Argument(..., help="Name of the sync to use"),
    branch: str = typer.Option(default=None, help="Branch to use for the sync."),
    diff: bool = typer.Option(default=True, help="Print the differences between the source and the destinatio before syncing"),
):
    """Synchronize the data between source and the destination systems for a given project."""
    sync_instance = get_instance(name=name)
    if not sync_instance:
        print_error_and_abort(f"Unable to find the sync {name}. Use the list command to see the sync available")

    ptd = get_potenda_from_instance(sync_instance, branch)
    ptd.load()
    
    mydiff = ptd.diff()
    
    if mydiff.has_diffs():
        if diff:
            mydiff.str()
        ptd.sync(diff=mydiff)
    else:
        typer.echo("No diffence found. Nothing to sync")


@app.command()
def generate(
    name: str = typer.Argument(..., help="Name of the sync to use"),
):
    """Generate all the python files for a given sync based on the configuration."""

    sync_instance = get_instance(name=name)
    if not sync_instance:
        print_error_and_abort(f"Unable to find the sync {name}. Use the list command to see the sync available")

    files_to_render = (
        ("diffsync_models.j2", "models.py"),
        ("diffsync_adapter.j2", "adapter.py"),
    )

    client = InfrahubClientSync()

    here = os.path.abspath(os.path.dirname(__file__))
    current_dir = str(os.getcwd())

    template_dir_absolute = str(os.path.join(here, "generator/templates"))
    template_dir_relative = template_dir_absolute.replace(current_dir, "")

    schema = client.schema.all()

    for adapter in [sync_instance.source, sync_instance.destination]:
        output_dir_absolute = str(os.path.join(sync_instance.directory, adapter.name))

        if not Path(output_dir_absolute).is_dir():
            Path(output_dir_absolute).mkdir(exist_ok=True)

        for item in files_to_render:
            render_template(
                template_dir=template_dir_relative,
                template_file=item[0],
                output_dir=output_dir_absolute,
                output_file=item[1],
                context={"schema": schema, "adapter": adapter, "config": sync_instance},
            )

            typer.echo(f"Saved {item[0]} in {item[1]}")
