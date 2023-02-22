import asyncio

import pytest

import infrahub.config as config

TEST_DATABASE = "infrahub.testing"

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
    config.SETTINGS.database.database = TEST_DATABASE
    config.SETTINGS.broker.enable = False
    config.SETTINGS.main.internal_address = "http://mock"