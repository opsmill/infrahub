import time
from pathlib import Path

import click
import common.events
import common.users
import gevent
from common.config import config
from locust import events
from locust.env import Environment
from locust.stats import PERCENTILES_TO_REPORT, StatsCSVFileWriter


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

    config.node_amount = amount
    config.attrs_amount = attrs
    config.rels_amount = rels

    env = Environment(user_classes=[user_class], events=events)
    env.custom_options = {
        "config": config,
        "stager": stager,
        "amount": amount,
        "attrs": attrs,
        "rels": rels,
        "schema": schema,
    }
    runner = env.create_local_runner()
    stats_csv_writer = StatsCSVFileWriter(env, PERCENTILES_TO_REPORT, str(time.time()), True)
    gevent.spawn(stats_csv_writer.stats_writer)
    runner.start(1, spawn_rate=1)
    runner.greenlet.join()

    print("--- done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
