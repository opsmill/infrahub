import asyncio

import pytest

from infrahub_sdk.ctl import config

pytest_plugins = ["pytester"]


@pytest.fixture(scope="session")
def event_loop():
    """Overrides pytest default function scoped event loop"""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def execute_before_any_test():
    config.load_and_exit()
    config.SETTINGS.server_address = "http://mock"
