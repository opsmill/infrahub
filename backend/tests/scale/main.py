import time
from pathlib import Path

import click
import common.events
import common.stagers
import common.users
import gevent
from common.config import Config as ScaleTestConfig
from infrahub_sdk import Config, InfrahubClientSync
from locust import events
from locust.env import Environment
from locust.stats import PERCENTILES_TO_REPORT, StatsCSVFileWriter

config = ScaleTestConfig()


def stage_environment(function: str, amount: int, attrs: int, rels: int, schema: Path):
    if function == "":
        return

    if not hasattr(common.stagers, function):
        raise ValueError(f"Invalid staging function provided: {function}")

    stager = getattr(common.stagers, function)
    if not callable(stager):
        raise ValueError(f"Invalid staging function provided: {function}")

    staging_client = InfrahubClientSync.init(
        address=config.url, config=Config(api_token=config.api_token, timeout=config.client_timeout)
    )
    print("--- loading load testing schema")

    # Generate extra attributes
    attributes = []
    for i in range(attrs):
        attributes.append({"name": f"attr{i}", "kind": "Text", "default_value": "", "optional": True})
    # Generate extra relationships
    relationships = []
    for i in range(rels):
        relationships.append(
            {
                "name": f"rel{i}",
                "kind": "Generic",
                "peer": "BuiltinTag",
                "cardinality": "one",
                "identifier": f"builtintag__infranode_{i}",
                "optional": True,
            }
        )

    common.stagers.load_schema(staging_client, schema, extra_attributes=attributes, relationships=relationships)
    print("--- done")

    time.sleep(5)
    print("--- staging load testing environment")
    stager(client=staging_client, amount=amount, attrs=attrs, rels=rels)

    print("--- 20s cool down period")
    time.sleep(20)


@click.command()
@click.option(
    "--schema",
    type=click.Path(exists=True, file_okay=True, dir_okay=False, path_type=Path),
    default="./schema.yml",
    help="Path to load testing schema file",
)
@click.option("--stager", default="", help="Function to use for staging the test environment")
@click.option(
    "--amount",
    default=0,
    type=click.IntRange(min=0, max=1_000_000_000),
    help="Amount of objects to be created in the `staging function`",
)
@click.option(
    "--attrs",
    default=0,
    type=click.IntRange(min=0, max=1_000_000_000),
    help="Amount of attributes per object to be created in the `staging function`",
)
@click.option(
    "--rels",
    default=0,
    type=click.IntRange(min=0, max=1_000_000_000),
    help="Amount of relationships per object to be created in the `staging function`",
)
@click.option("--test", default="InfrahubClientUser", help="The Locust test user class")
def main(schema: Path, stager: str, amount: int, attrs: int, rels: int, test: str) -> int:
    if not hasattr(common.users, test):
        print(f"Invalid test class provided: {test}")
        return 1

    user_class = getattr(common.users, test)

    stage_environment(function=stager, amount=amount, attrs=attrs, rels=rels, schema=schema)

    print("--- starting test")
    env = Environment(user_classes=[user_class], events=events)
    runner = env.create_local_runner()

    stats_csv_writer = StatsCSVFileWriter(env, PERCENTILES_TO_REPORT, str(time.time()), True)
    gevent.spawn(stats_csv_writer.stats_writer)

    runner.start(1, spawn_rate=1)
    runner.greenlet.join()

    print("--- done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
