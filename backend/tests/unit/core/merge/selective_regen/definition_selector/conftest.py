from __future__ import annotations

import logging

import pytest
from infrahub_sdk import Config, InfrahubClient

from infrahub.core.merge.selective_regen.definition_selector.artifact_selector import ArtifactSelector
from infrahub.core.merge.selective_regen.definition_selector.generator_selector import GeneratorSelector
from infrahub.core.merge.selective_regen.gate import DefinitionGate
from infrahub.core.merge.selective_regen.impacted import ImpactedSubscriberResolver


@pytest.fixture
def client() -> InfrahubClient:
    return InfrahubClient(config=Config(address="http://mock"))


@pytest.fixture
def log() -> logging.Logger:
    return logging.getLogger("test")


@pytest.fixture
def gate(log: logging.Logger) -> DefinitionGate:
    return DefinitionGate(log=log)


@pytest.fixture
def impacted_resolver(client: InfrahubClient) -> ImpactedSubscriberResolver:
    return ImpactedSubscriberResolver(client=client)


@pytest.fixture
def artifact_selector(
    client: InfrahubClient, gate: DefinitionGate, impacted_resolver: ImpactedSubscriberResolver, log: logging.Logger
) -> ArtifactSelector:
    return ArtifactSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log)


@pytest.fixture
def generator_selector(
    client: InfrahubClient, gate: DefinitionGate, impacted_resolver: ImpactedSubscriberResolver, log: logging.Logger
) -> GeneratorSelector:
    return GeneratorSelector(client=client, gate=gate, impacted_resolver=impacted_resolver, log=log)
