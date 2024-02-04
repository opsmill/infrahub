import time
from pathlib import Path

import click
import common.events
import common.stagers
import common.users
from common.config import Config as ScaleTestConfig
from infrahub_sdk import Config, InfrahubClientSync
from locust import events
from locust.env import Environment

config = ScaleTestConfig()


def stage_environment(function: str, amount: int, attrs: int, schema: Path):
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
    attributes = []
    for i in range(attrs):
        attributes.append({"name": f"test{i}", "kind": "Text", "default_value": "", "optional": True})

    common.stagers.load_schema(staging_client, schema, extra_attributes=attributes)
    print("--- done")

    time.sleep(5)
    print("--- staging load testing environment")
    stager(client=staging_client, amount=amount, attrs=attrs)

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
@click.option("--test", default="InfrahubClientUser", help="The Locust test user class")
def main(schema: Path, stager: str, amount: int, attrs: int, test: str) -> int:
    if not hasattr(common.users, test):
        print(f"Invalid test class provided: {test}")
        return 1

    user_class = getattr(common.users, test)

    stage_environment(function=stager, amount=amount, attrs=attrs, schema=schema)

    print("--- starting test")
    env = Environment(user_classes=[user_class], events=events)
    runner = env.create_local_runner()
    runner.start(1, spawn_rate=1)
    runner.greenlet.join()

    print("--- done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
