from pathlib import Path
from typing import Any

import typer
from infrahub_sdk.async_typer import AsyncTyper
from rich.progress import (
    Progress,
)

from infrahub import config
from infrahub.core import registry
from infrahub.core.constants import InfrahubKind
from infrahub.core.graph.constraints import ConstraintManagerNeo4j
from infrahub.core.graph.index import node_indexes, rel_indexes
from infrahub.core.graph.schema import GRAPH_SCHEMA
from infrahub.core.initialization import create_branch, first_time_initialization, initialization
from infrahub.core.manager import NodeManager
from infrahub.core.query import Query
from infrahub.core.schema import SchemaRoot
from infrahub.core.utils import delete_all_nodes
from infrahub.core.validators.uniqueness.model import NodeUniquenessQueryRequest
from infrahub.core.validators.uniqueness.query import NodeUniqueAttributeConstraintQuery
from infrahub.database import InfrahubDatabaseMode, get_db
from infrahub.database.analyzer import InfrahubDatabaseAnalyzer, query_stats
from infrahub.lock import initialize_lock
from infrahub.log import get_logger
from infrahub.test_data.gen_connected_nodes import GenerateConnectedNodes
from infrahub.test_data.gen_isolated_node import GenerateIsolatedNodes
from infrahub.test_data.gen_node_profile_node import ProfileAttribute
from infrahub.test_data.gen_branched_attributes_nodes import GenerateBranchedAttributeNodes

app = AsyncTyper()

log = get_logger()


@app.command()
async def isolated_node(
    test_name: str = "isolated_node",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    default_branch = await registry.get_branch(db=db)
    tag_schema = registry.schema.get_node_schema(name=InfrahubKind.TAG, branch=default_branch)

    query_stats.name = test_name
    query_stats.measure_memory_usage = True
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = GenerateIsolatedNodes(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_50_tag", task=NodeManager.query, limit=50, schema=tag_schema)
        await loader.load_data(nbr_tags=count, nbr_repository=count)

    query_stats.create_graphs()


@app.command()
async def connected_nodes(
    test_name: str = "connected_nodes",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    default_branch = await registry.get_branch(db=db)
    tag_schema = registry.schema.get_node_schema(name=InfrahubKind.TAG, branch=default_branch)

    query_stats.name = test_name
    query_stats.measure_memory_usage = True
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = GenerateConnectedNodes(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_50_tag", task=NodeManager.query, limit=50, schema=tag_schema)
        await loader.load_data(nbr_tags=count, nbr_repository=count)

    query_stats.create_graphs()


@app.command()
async def node_constraints_uniqueness(
    test_name: str = "node_constraints_uniqueness",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    db.manager.index.init(nodes=node_indexes, rels=rel_indexes)

    constraint_manager = ConstraintManagerNeo4j.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    async with db.start_transaction() as dbt:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=dbt)

        log.info("Remove existing constraints & indexes")
        await dbt.manager.index.drop()
        await constraint_manager.drop()

        await constraint_manager.add()
        await first_time_initialization(db=dbt)

    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    default_branch = await registry.get_branch(db=db)

    query_stats.name = test_name
    query_stats.measure_memory_usage = True
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    query_unique_tag_name = await NodeUniqueAttributeConstraintQuery.init(
        db=db,
        branch=default_branch,
        query_request=NodeUniquenessQueryRequest(
            kind=InfrahubKind.TAG, unique_attribute_paths=[{"attribute_name": "name", "property_name": "value"}]
        ),
    )

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = GenerateConnectedNodes(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_unique_tag_name", task=query_unique_tag_name.execute)

        await loader.load_data(nbr_tags=count, nbr_repository=count)

    query_stats.create_graphs()


@app.command()
async def profile_attribute(
    test_name: str = "profile_attribute",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    db.manager.index.init(nodes=node_indexes, rels=rel_indexes)

    constraint_manager = ConstraintManagerNeo4j.from_graph_schema(db=db, schema=GRAPH_SCHEMA)

    async with db.start_transaction() as dbt:
        log.info("Delete All Nodes")
        await delete_all_nodes(db=dbt)

        log.info("Remove existing constraints & indexes")
        await dbt.manager.index.drop()
        await constraint_manager.drop()

        await constraint_manager.add()
        await first_time_initialization(db=dbt)

    log.info("Starting initialization .. ")
    initialize_lock()
    await initialization(db=db)

    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
                "relationships": [
                    {"name": "owner", "peer": "TestPerson", "optional": False, "cardinality": "one"},
                ],
            },
            {
                "name": "Person",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value"],
                "order_by": ["height__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "height", "kind": "Number", "optional": True},
                ],
                "relationships": [{"name": "cars", "peer": "TestCar", "cardinality": "many"}],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)

    default_branch = await registry.get_branch(db=db)

    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    person_schema = registry.schema.get_node_schema(name="TestPerson", branch=default_branch)

    query_stats.name = test_name
    query_stats.measure_memory_usage = False
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    with Progress() as progress:
        loader = ProfileAttribute(db=db, progress=progress, concurrent_execution=parallel)
        loader.add_callback(callback_name="query_50_person", task=NodeManager.query, limit=50, schema=person_schema)
        await loader.load_data(nbr_person=count)

    query_stats.create_graphs()


@app.command()
async def get_filtered_nodes_simple(
    test_name: str = "branched_attributes_node",
    config_file: str = typer.Option("infrahub.toml", envvar="INFRAHUB_CONFIG"),
    count: int = typer.Option(1000),
    parallel: int = typer.Option(5),
    use_old: bool = False,
) -> None:
    config.load_and_exit(config_file_name=config_file)

    db = InfrahubDatabaseAnalyzer(mode=InfrahubDatabaseMode.DRIVER, driver=await get_db())
    log.info("Starting initialization .. ")
    initialize_lock()

    await initialization(db=db)

    SCHEMA: dict[str, Any] = {
        "nodes": [
            {
                "name": "Car",
                "namespace": "Test",
                "default_filter": "name__value",
                "display_labels": ["name__value", "color__value"],
                "attributes": [
                    {"name": "name", "kind": "Text", "unique": True},
                    {"name": "nbr_seats", "kind": "Number"},
                    {"name": "color", "kind": "Text", "default_value": "#444444", "max_length": 7},
                    {"name": "is_electric", "kind": "Boolean"},
                ],
            },
        ],
    }

    schema = SchemaRoot(**SCHEMA)
    default_branch = await registry.get_branch(db=db)
    registry.schema.register_schema(schema=schema, branch=default_branch.name)

    query_stats.name = test_name
    query_stats.measure_memory_usage = False
    query_stats.output_location = Path.cwd() / "query_performance_results"
    query_stats.start_tracking()

    log.info("Start loading data .. ")
    branch = await create_branch(db=db, branch_name="branch")
    with Progress() as progress:
        loader = GenerateBranchedAttributeNodes(db=db, progress=progress, concurrent_execution=parallel)
        if use_old:
            loader.add_callback(callback_name="query_nbr_seats_old", task=run_old_simple_filter)
        else:
            loader.add_callback(callback_name="query_nbr_seats_new", task=run_new_simple_filter)
        await loader.load_data(nbr_cars=count, branch_name=branch.name)

    query_stats.create_graphs()


async def run_old_simple_filter(db: InfrahubDatabaseAnalyzer):
    default_branch = await registry.get_branch(db=db)
    query = await SimpleOldFilterQuery.init(
        db=db,
        branch=default_branch,
    )
    await query.execute(db=db)
    query.get_results()


class SimpleOldFilterQuery(Query):
    name = "query_filter_old"

    async def query_init(self, db, **kwargs: Any) -> None:

        branch_filter, branch_params = self.branch.get_query_filter_path()
        self.params = branch_params
        query = """
        CYPHER runtime = parallel
        MATCH p = (n:Node)
        WHERE "TestCar" IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN r
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH n, r as rb
        WHERE rb.status = "active"
        CALL {
            WITH n
            MATCH path = (n)-[:HAS_ATTRIBUTE]-(i:Attribute { name: "nbr_seats" })-[:HAS_VALUE]-(av:AttributeValue)
            WHERE (av.value = 7 OR av.is_default) AND all(r IN relationships(path) WHERE %(branch_filter)s)
            WITH
            n,
            path,
            reduce(br_lvl = 0, r in relationships(path) | br_lvl + r.branch_level) AS branch_level,
            [i IN relationships(path) | i.from] AS froms,
            all(r IN relationships(path) WHERE r.status = "active") AS is_active, av
            ORDER BY branch_level DESC, froms[-1] DESC, froms[-2] DESC
            WITH head(collect([is_active, n, av])) AS latest_node_details
            WHERE latest_node_details[0] = TRUE
            WITH latest_node_details[1] AS n, latest_node_details[2] AS av
            RETURN n AS filter1, av.value AS attr1_node_value, av.is_default AS attr1_is_default
        }
        WITH filter1 as n, rb, attr1_node_value, attr1_is_default
        WHERE attr1_node_value = 7
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query=query)
        self.return_labels = ["n.uuid", "rb.branch", "ID(rb) as rb_id"]

async def run_new_simple_filter(db: InfrahubDatabaseAnalyzer):
    default_branch = await registry.get_branch(db=db)
    query = await SimpleNewFilterQuery.init(
        db=db,
        branch=default_branch,
    )
    await query.execute(db=db)
    query.get_results()


class SimpleNewFilterQuery(Query):
    name = "query_filter_new"

    async def query_init(self, db, **kwargs: Any) -> None:
        branch_filter, branch_params = self.branch.get_query_filter_path()
        self.params = branch_params
        query = """
        CYPHER runtime = parallel
        MATCH (n:Node)
        WHERE "TestCar" IN LABELS(n)
        CALL {
            WITH n
            MATCH (root:Root)<-[r:IS_PART_OF]-(n)
            WHERE %(branch_filter)s
            RETURN r AS rb
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH rb, n
        WHERE rb.status = "active"
        CALL {
            WITH n
            MATCH (n)-[r:HAS_ATTRIBUTE]-(attr:Attribute { name: "nbr_seats" })
            WHERE %(branch_filter)s
            RETURN attr, r AS r_attr
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH rb, n, r_attr, attr
        WHERE r_attr.status = "active"
        CALL {
            WITH attr
            MATCH (attr)-[r:HAS_VALUE]-(av:AttributeValue)
            WHERE %(branch_filter)s
            AND (av.value = 7 or av.is_default)
            RETURN r AS r_attr_val, av
            ORDER BY r.branch_level DESC, r.from DESC
            LIMIT 1
        }
        WITH rb, n, r_attr, attr, r_attr_val, av
        WHERE r_attr_val.status = "active"
        AND av.value = 7
        """ % {"branch_filter": branch_filter}
        self.add_to_query(query=query)
        self.return_labels = ["n.uuid", "rb.branch", "ID(rb) as rb_id"]

if __name__ == "__main__":
    app()
