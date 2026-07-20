from __future__ import annotations

import logging

import pytest
from infrahub_sdk import Config, InfrahubClient


@pytest.fixture
def client() -> InfrahubClient:
    return InfrahubClient(config=Config(address="http://mock"))


@pytest.fixture
def log() -> logging.Logger:
    return logging.getLogger("test")
