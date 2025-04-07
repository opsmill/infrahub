from __future__ import annotations

import importlib
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import typer
import ujson
from infrahub_sdk.async_typer import AsyncTyper
from prefect.testing.utilities import prefect_test_harness
from pydantic import BaseModel
from rich import print as rprint
from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress
from rich.table import Table

from infrahub import config
from infrahub.core import registry
from infrahub.core.graph import GRAPH_VERSION
from infrahub.core.graph.constraints import ConstraintManagerBase, ConstraintManagerMemgraph, ConstraintManagerNeo4j
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.core.initialization import (
    first_time_initialization,
    get_root_node,
    initialization,
    initialize_registry,
)
from infrahub.core.migrations.graph import get_graph_migrations
from infrahub.core.migrations.schema.models import SchemaApplyMigrationData
from infrahub.core.migrations.schema.tasks import schema_apply_migrations
from infrahub.core.schema import SchemaRoot, core_models, internal_schema
from infrahub.core.schema.definitions.deprecated import deprecated_models
from infrahub.core.schema.manager import SchemaManager
from infrahub.core.utils import delete_all_nodes
from infrahub.core.validators.models.validate_migration import SchemaValidateMigrationData
from infrahub.core.validators.tasks import schema_validate_migrations
from infrahub.database import DatabaseType
from infrahub.log import get_logger
from infrahub.services import InfrahubServices
from infrahub.services.adapters.message_bus.local import BusSimulator
from infrahub.services.adapters.workflow.local import WorkflowLocalExecution

from .constants import ERROR_BADGE, FAILED_BADGE, SUCCESS_BADGE

if TYPE_CHECKING:
    from infrahub.cli.context import CliContext
    from infrahub.database import InfrahubDatabase

app = AsyncTyper()

PERMISSIONS_AVAILABLE = ["read", "write", "admin"]


class ConstraintAction(str, Enum):
    SHOW = "show"
    ADD = "add"
    DROP = "drop"


class IndexAction(str, Enum):
    SHOW = "show"
    ADD = "add"
    DROP = "drop"


@app.callback()
def callback() -> None:
    """
    Manage the graph in the database.
    """


@app.command()
async def init(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
) -> None:
    """Erase the content of the database and initialize it with the core schema."""

    log = get_logger()

    # --------------------------------------------------
    # CLEANUP
    #  - For now we delete everything in the database
    #   TODO, if possible try to implement this in an idempotent way
    # --------------------------------------------------

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)
    async with dbdriver.start_transaction() as db:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=db)
        await first_time_initialization(db=db)

    await dbdriver.close()


@app.command()
async def load_test_data(
    ctx: typer.Context,
    config_file: str = typer.Option(
        "infrahub.toml", envvar="INFRAHUB_CONFIG", help="Location of the configuration file to use for Infrahub"
    ),
    dataset: str = "dataset01",
) -> None:
    """Load test data into the database from the `test_data` directory."""

    logging.getLogger("neo4j").setLevel(logging.ERROR)
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    async with dbdriver.start_session() as db:
        await initialization(db=db)

        log_level = "DEBUG"

        FORMAT = "%(message)s"
        logging.basicConfig(level=log_level, format=FORMAT, datefmt="[%X]", handlers=[RichHandler()])
        logging.getLogger("infrahub")

        dataset_module = importlib.import_module(f"infrahub.test_data.{dataset}")
        await dataset_module.load_data(db=db)

    await dbdriver.close()


@app.command(name="migrate")
async def migrate_cmd(
    ctx: typer.Context,
    check: bool = typer.Option(False, help="Check the state of the database without applying the migrations."),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    await migrate_database(db=dbdriver, initialize=True, check=check)

    await dbdriver.close()


@app.command(name="update-core-schema")
async def update_core_schema_cmd(
    ctx: typer.Context,
    debug: bool = typer.Option(False, help="Enable advanced logging and troubleshooting"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Check the current format of the internal graph and apply the necessary migrations"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)
    os.environ["PREFECT_SERVER_ANALYTICS_ENABLED"] = "false"

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    service = await InfrahubServices.new(
        database=dbdriver, message_bus=BusSimulator(), workflow=WorkflowLocalExecution()
    )

    with prefect_test_harness():
        await update_core_schema(db=dbdriver, service=service, initialize=True, debug=debug)

    await dbdriver.close()


@app.command()
async def constraint(
    ctx: typer.Context,
    action: ConstraintAction = typer.Argument(ConstraintAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Constraints"""
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    manager: ConstraintManagerBase | None = None
    if dbdriver.db_type == DatabaseType.NEO4J:
        manager = ConstraintManagerNeo4j.from_graph_schema(db=dbdriver, schema=GRAPH_SCHEMA)
    elif dbdriver.db_type == DatabaseType.MEMGRAPH:
        manager = ConstraintManagerMemgraph.from_graph_schema(db=dbdriver, schema=GRAPH_SCHEMA)
    else:
        print(f"Database type not supported : {dbdriver.db_type}")
        raise typer.Exit(1)

    if action == ConstraintAction.ADD:
        await manager.add()
    elif action == ConstraintAction.DROP:
        await manager.drop()

    constraints = await manager.list()

    console = Console()

    table = Table(title="Database Constraints")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Property")

    for item in constraints:
        table.add_row(item.item_name, item.item_label, item.property)

    console.print(table)

    await dbdriver.close()


@app.command()
async def index(
    ctx: typer.Context,
    action: IndexAction = typer.Argument(IndexAction.SHOW),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Manage Database Indexes"""
    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)
    dbdriver.manager.index.init(nodes=node_indexes, rels=rel_indexes)

    if action == IndexAction.ADD:
        await dbdriver.manager.index.add()
    elif action == IndexAction.DROP:
        await dbdriver.manager.index.drop()

    indexes = await dbdriver.manager.index.list()

    console = Console()

    table = Table(title="Database Indexes")

    table.add_column("Name", justify="right", style="cyan", no_wrap=True)
    table.add_column("Label")
    table.add_column("Property")
    table.add_column("Type")
    table.add_column("Entity Type")

    for item in indexes:
        table.add_row(
            item.name, item.label, ", ".join(item.properties), item.type.value.upper(), item.entity_type.value.upper()
        )

    console.print(table)

    await dbdriver.close()


async def migrate_database(db: InfrahubDatabase, initialize: bool = False, check: bool = False) -> None:
    """Apply the latest migrations to the database, this function will print the status directly in the console.

    This function is expected to run on an empty

    Args:
        db: The database object.
        check: If True, the function will only check the status of the database and not apply the migrations. Defaults to False.
    """
    rprint("Checking current state of the Database")

    if initialize:
        await initialize_registry(db=db)

    root_node = await get_root_node(db=db)
    migrations = await get_graph_migrations(root=root_node)

    if not migrations:
        rprint(f"Database up-to-date (v{root_node.graph_version}), no migration to execute.")
        return

    rprint(
        f"Database needs to be updated (v{root_node.graph_version} -> v{GRAPH_VERSION}), {len(migrations)} migrations pending"
    )

    if check:
        return

    for migration in migrations:
        execution_result = await migration.execute(db=db)
        validation_result = None

        if execution_result.success:
            validation_result = await migration.validate_migration(db=db)
            if validation_result.success:
                rprint(f"Migration: {migration.name} {SUCCESS_BADGE}")
                root_node.graph_version = migration.minimum_version + 1
                await root_node.save(db=db)

        if not execution_result.success or validation_result and not validation_result.success:
            rprint(f"Migration: {migration.name} {FAILED_BADGE}")
            for error in execution_result.errors:
                rprint(f"  {error}")
            if validation_result and not validation_result.success:
                for error in validation_result.errors:
                    rprint(f"  {error}")
            break


async def initialize_internal_schema() -> None:
    registry.schema = SchemaManager()
    schema = SchemaRoot(**internal_schema)
    registry.schema.register_schema(schema=schema)


async def update_core_schema(
    db: InfrahubDatabase, service: InfrahubServices, initialize: bool = True, debug: bool = False
) -> None:
    """Update the core schema of Infrahub to the latest version"""
    # ----------------------------------------------------------
    # Initialize Schema and Registry
    # ----------------------------------------------------------
    if initialize:
        await initialize_registry(db=db)
        await initialize_internal_schema()

    default_branch = registry.get_branch_from_registry(branch=registry.default_branch)

    # ----------------------------------------------------------
    # Load Current Schema from the database
    # ----------------------------------------------------------
    schema_default_branch = await registry.schema.load_schema_from_db(db=db, branch=default_branch)
    registry.schema.set_schema_branch(name=default_branch.name, schema=schema_default_branch)
    branch_schema = registry.schema.get_schema_branch(name=registry.default_branch)

    candidate_schema = branch_schema.duplicate()
    candidate_schema.load_schema(schema=SchemaRoot(**internal_schema))
    candidate_schema.load_schema(schema=SchemaRoot(**core_models))
    candidate_schema.load_schema(schema=SchemaRoot(**deprecated_models))
    candidate_schema.process()

    schema_diff = branch_schema.diff(other=candidate_schema)
    branch_schema.validate_node_deletions(diff=schema_diff)
    result = branch_schema.validate_update(other=candidate_schema, diff=schema_diff, enforce_update_support=False)
    if result.errors:
        rprint(f"{ERROR_BADGE} | Unable to update the schema, due to failed validations")
        for error in result.errors:
            rprint(error.to_string())
        raise typer.Exit(1)

    if not result.diff.all:
        rprint("Core Schema Up to date, nothing to update")
        return

    rprint("Core Schema has diff, will need to be updated")
    if debug:
        result.diff.print()

    # ----------------------------------------------------------
    # Validate if the new schema is valid with the content of the database
    # ----------------------------------------------------------
    validate_migration_data = SchemaValidateMigrationData(
        branch=default_branch,
        schema_branch=candidate_schema,
        constraints=result.constraints,
    )
    responses = await schema_validate_migrations(message=validate_migration_data, service=service)
    error_messages = [violation.message for response in responses for violation in response.violations]
    if error_messages:
        rprint(f"{ERROR_BADGE} | Unable to update the schema, due to failed validations")
        for message in error_messages:
            rprint(message)
        raise typer.Exit(1)

    # ----------------------------------------------------------
    # Update the schema
    # ----------------------------------------------------------
    origin_schema = branch_schema.duplicate()

    # Update the internal schema
    schema_default_branch.load_schema(schema=SchemaRoot(**internal_schema))
    schema_default_branch.process()
    registry.schema.set_schema_branch(name=default_branch.name, schema=schema_default_branch)

    async with db.start_transaction() as dbt:
        await registry.schema.update_schema_branch(
            schema=candidate_schema,
            db=dbt,
            branch=default_branch.name,
            diff=result.diff,
            limit=result.diff.all,
            update_db=True,
        )
        default_branch.update_schema_hash()
        rprint("The Core Schema has been updated")
        if debug:
            rprint(f"New schema hash: {default_branch.active_schema_hash.main}")
        await default_branch.save(db=dbt)

    # ----------------------------------------------------------
    # Run the migrations
    # ----------------------------------------------------------
    apply_migration_data = SchemaApplyMigrationData(
        branch=default_branch,
        new_schema=candidate_schema,
        previous_schema=origin_schema,
        migrations=result.migrations,
    )
    migration_error_msgs = await schema_apply_migrations(message=apply_migration_data, service=service)

    if migration_error_msgs:
        rprint(f"{ERROR_BADGE} | Some error(s) happened while running the schema migrations")
        for message in migration_error_msgs:
            rprint(message)
        raise typer.Exit(1)


class SerialVertex(BaseModel):
    db_id: str
    labels: list[str]
    kind: str | None
    uuid: str | None
    name: str | None
    branch_support: str | None

    def __hash__(self) -> int:
        return hash(self.db_id)

    @property
    def frozen_labels(self) -> frozenset[str]:
        return frozenset(self.labels)


class SerialEdge(BaseModel):
    db_id: str
    edge_type: str
    start_node_id: str
    end_node_id: str
    properties: dict[str, str | int | None | bool]

    def __hash__(self) -> int:
        return hash(self.db_id)


@app.command(name="selected-export")
async def selected_export_cmd(
    ctx: typer.Context,
    kinds: list[str] = typer.Option([], help="Node kinds to export"),  # noqa: B008
    uuids: list[str] = typer.Option([], help="UUIDs of nodes to export"),  # noqa: B008
    query_limit: int = typer.Option(1000, help="Maximum batch size of export query"),  # noqa: B008
    export_dir: Path = typer.Option(Path("infrahub-exports"), help="Path of directory to save exports"),  # noqa: B008
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Export database structure of selected nodes from the database without any actual data"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    await selected_export(db=dbdriver, kinds=kinds, uuids=uuids, export_dir=export_dir, query_limit=query_limit)

    await dbdriver.close()


async def selected_export(
    db: InfrahubDatabase,
    kinds: list[str],
    uuids: list[str],
    export_dir: Path,
    query_limit: int = 1000,
) -> None:
    query = """
// --------------
// filter nodes
// --------------
MATCH (n:Node)
WHERE ($kinds IS NULL OR size($kinds) = 0 OR any(l IN labels(n) WHERE l in $kinds))
AND ($uuids IS NULL OR size($uuids) = 0 OR n.uuid IN $uuids)
WITH n
// --------------
// pagination
// --------------
ORDER BY %(id_func)s(n)
SKIP toInteger($offset)
LIMIT toInteger($limit)
CALL {
    // --------------
    // get all the nodes and edges linked to this node up to 2 steps away, excluding IS_PART_OF
    // --------------
    WITH n
    MATCH (n)-[r1]-(v1)-[r2]-(v2)
    WHERE type(r1) <> "IS_PART_OF"
    WITH collect([v1, v2]) AS vertex_pairs, collect([r1, r2]) AS edge_pairs
    WITH reduce(
        vertices = [], v_pair IN vertex_pairs |
        CASE
            WHEN NOT v_pair[0] IN vertices AND NOT v_pair[1] IN vertices THEN vertices + v_pair
            WHEN NOT v_pair[0] IN vertices THEN vertices + [v_pair[0]]
            WHEN NOT v_pair[1] IN vertices THEN vertices + [v_pair[1]]
            ELSE vertices
        END
    ) AS vertices,
    reduce(
        edges = [], e_pair IN edge_pairs |
        CASE
            WHEN NOT e_pair[0] IN edges AND NOT e_pair[1] IN edges THEN edges + e_pair
            WHEN NOT e_pair[0] IN edges THEN edges + [e_pair[0]]
            WHEN NOT e_pair[1] IN edges THEN edges + [e_pair[1]]
            ELSE edges
        END
    ) AS edges
    RETURN vertices, edges
}
// --------------
// include the root and IS_PART_OF edges
// --------------
OPTIONAL MATCH (n)-[root_edge:IS_PART_OF]->(root:Root)
WITH n, vertices, edges, root, collect(root_edge) AS root_edges
WITH vertices + [n, root] AS vertices, edges + root_edges AS edges
// --------------
// serialize the vertices
// --------------
CALL {
    WITH vertices
    UNWIND vertices AS vertex
    WITH {
        db_id: %(id_func)s(vertex),
        kind: vertex.kind,
        labels: labels(vertex),
        uuid: vertex.uuid,
        name: vertex.name,
        branch_support: vertex.branch_support
    } AS serial_vertex
    RETURN collect(serial_vertex) AS serial_vertices
}
// --------------
// serialize the nodes
// --------------
CALL {
    WITH edges
    UNWIND edges AS edge
    WITH {
        db_id: %(id_func)s(edge),
        edge_type: type(edge),
        start_node_id: %(id_func)s(startNode(edge)),
        end_node_id: %(id_func)s(endNode(edge)),
        properties: properties(edge)
    } AS serial_edge
    RETURN collect(serial_edge) AS serial_edges
}
RETURN serial_vertices, serial_edges
    """ % {"id_func": db.get_id_function_name()}
    timestamp_str = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    has_more_data = True
    limit = query_limit
    offset = 0
    all_vertices: set[SerialVertex] = set()
    all_edges: set[SerialEdge] = set()
    while has_more_data:
        results = await db.execute_query(
            query=query,
            params={"kinds": kinds, "uuids": uuids, "limit": limit, "offset": offset},
        )
        has_more_data = len(results) >= limit
        offset += limit

        for result in results:
            serial_vertices = result.get("serial_vertices")
            all_vertices.update(SerialVertex(**serial_vertex) for serial_vertex in serial_vertices)
            serial_edges = result.get("serial_edges")
            all_edges.update(SerialEdge(**serial_edge) for serial_edge in serial_edges)

    export_dir /= Path(f"export-{timestamp_str}")
    if not export_dir.exists():
        export_dir.mkdir(parents=True)

    vertex_path = export_dir / Path("vertices.json")
    vertex_path.touch(exist_ok=True)
    with vertex_path.open(mode="w") as file:
        for serial_vertex in all_vertices:
            vertex_json = serial_vertex.model_dump_json()
            file.write(f"{vertex_json}\n")
    edge_path = export_dir / Path("edges.json")
    edge_path.touch(exist_ok=True)
    with edge_path.open(mode="w") as file:
        for serial_edge in all_edges:
            vertex_edge = serial_edge.model_dump_json()
            file.write(f"{vertex_edge}\n")
    rprint(f"{SUCCESS_BADGE} Export complete")
    rprint(f"Export directory is here: {export_dir.absolute()}")


@app.command(name="load-export", hidden=True)
async def load_export_cmd(
    ctx: typer.Context,
    export_dir: Path = typer.Argument(help="Path to export directory"),
    query_limit: int = typer.Option(1000, help="Maximum batch size of import query"),
    config_file: str = typer.Argument("infrahub.toml", envvar="INFRAHUB_CONFIG"),
) -> None:
    """Load an anonymized export into neo4j"""
    logging.getLogger("infrahub").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.ERROR)
    logging.getLogger("prefect").setLevel(logging.ERROR)

    config.load_and_exit(config_file_name=config_file)

    context: CliContext = ctx.obj
    dbdriver = await context.init_db(retry=1)

    await load_export(db=dbdriver, export_dir=export_dir, query_limit=query_limit)

    await dbdriver.close()


async def load_export(db: InfrahubDatabase, export_dir: Path, query_limit: int = 1000) -> None:
    if not export_dir.exists():
        rprint(f"{ERROR_BADGE} {export_dir} does not exist")
        raise typer.Exit(1)
    if not export_dir.is_dir():
        rprint(f"{ERROR_BADGE} {export_dir} is not a directory")
        raise typer.Exit(1)
    vertex_file: Path | None = None
    edge_file: Path | None = None

    for export_file in export_dir.glob("*.json"):
        if export_file.name == "vertices.json":
            vertex_file = export_file
        elif export_file.name == "edges.json":
            edge_file = export_file
    if not vertex_file or not vertex_file.exists() or not vertex_file.is_file():
        rprint(f"{ERROR_BADGE} File 'vertices.json' does not exist in the export directory")
        raise typer.Exit(1)
    if not edge_file or not edge_file.exists() or not edge_file.is_file():
        rprint(f"{ERROR_BADGE} File 'edges.json' does not exist in the export directory")
        raise typer.Exit(1)

    rprint("Reading vertices file...", end="")
    vertices_by_labels_map: dict[frozenset[str], set[SerialVertex]] = defaultdict(set)
    vertices_count = 0
    with vertex_file.open() as file:
        while True:
            raw_line = file.readline()
            if not raw_line:
                break
            vertex_dict = ujson.loads(raw_line)
            vertex_object = SerialVertex.model_construct(**vertex_dict)
            vertices_by_labels_map[vertex_object.frozen_labels].add(vertex_object)
            vertices_count += 1
    rprint("done")
    rprint("Reading edges file...", end="")
    edges_by_type_map: dict[str, set[SerialEdge]] = defaultdict(set)
    edges_count = 0
    with edge_file.open() as file:
        while True:
            raw_line = file.readline()
            if not raw_line:
                break
            edge_dict = ujson.loads(raw_line)
            edge_object = SerialEdge.model_construct(**edge_dict)
            edges_by_type_map[edge_object.edge_type].add(edge_object)
            edges_count += 1
    rprint("done")

    with Progress() as progress:
        vertex_task = progress.add_task("Loading vertices", total=vertices_count)
        edges_task = progress.add_task("Loading edges", total=edges_count)

        for labels_set, vertices in vertices_by_labels_map.items():
            vertex_import_query = """
UNWIND $vertices AS vertex
CREATE (:%(node_labels)s {db_id: vertex.db_id, kind: vertex.kind, uuid: vertex.uuid, name: vertex.name, branch_support: vertex.branch_support})
            """ % {"node_labels": ":".join(labels_set)}
            vertices_list = list(vertices)
            for v_start in range(0, len(vertices), query_limit):
                vertex_batch = vertices_list[v_start : v_start + query_limit]
                vertex_dicts = [v.model_dump(exclude={"labels"}) for v in vertex_batch]
                await db.execute_query(query=vertex_import_query, params={"vertices": vertex_dicts})
                progress.update(vertex_task, advance=len(vertex_dicts))

        for edge_type, edges in edges_by_type_map.items():
            edges_import_query = """
UNWIND $edges AS edge
MATCH (a) WHERE a.db_id = edge.start_node_id
MATCH (b) WHERE b.db_id = edge.end_node_id
CREATE (a)-[e:%(edge_type)s]->(b)
SET e = edge.properties
            """ % {"edge_type": edge_type}
            edges_list = list(edges)
            for e_start in range(0, len(edges), query_limit):
                edge_batch = edges_list[e_start : e_start + query_limit]
                edge_dicts = [e.model_dump(exclude={"db_id"}) for e in edge_batch]
                await db.execute_query(query=edges_import_query, params={"edges": edge_dicts})
                progress.update(edges_task, advance=len(edge_dicts))
    rprint(f"{SUCCESS_BADGE} Export loaded")
