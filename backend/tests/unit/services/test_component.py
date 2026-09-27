from __future__ import annotations

from dataclasses import dataclass

import pytest

from infrahub.services.component import COMPONENT_API_SERVER, COMPONENT_GIT_AGENT, WorkerInfo


@dataclass
class AttributionCase:
    name: str
    keys: list[str]
    expected_component: str | None
    expected_active: bool


ATTRIBUTION_CASES = [
    AttributionCase(
        name="active_key_names_the_component",
        keys=["workers:active:git_agent:worker:w1", "workers:worker:w1"],
        expected_component=COMPONENT_GIT_AGENT,
        expected_active=True,
    ),
    AttributionCase(
        # A process that stopped heartbeating keeps its schema-hash key for a while,
        # which still says what it ran as, whatever the branch segment holds.
        name="schema_hash_key_attributes_an_exited_process",
        keys=["workers:schema_hash:branch:3f2a-branch:api_server:worker:w1", "workers:worker:w1"],
        expected_component=COMPONENT_API_SERVER,
        expected_active=False,
    ),
    AttributionCase(
        name="resource_key_names_the_component",
        keys=["workers:resources:api_server:worker:w1"],
        expected_component=COMPONENT_API_SERVER,
        expected_active=False,
    ),
    AttributionCase(
        name="presence_key_alone_leaves_the_process_unattributed",
        keys=["workers:worker:w1"],
        expected_component=None,
        expected_active=False,
    ),
    AttributionCase(
        name="an_unknown_component_name_is_not_taken_on_trust",
        keys=["workers:active:scheduler:worker:w1"],
        expected_component=None,
        expected_active=True,
    ),
]


@pytest.mark.parametrize("case", ATTRIBUTION_CASES, ids=[case.name for case in ATTRIBUTION_CASES])
def test_worker_is_attributed_to_the_component_its_keys_name(case: AttributionCase) -> None:
    worker = WorkerInfo(identity="w1")

    for key in case.keys:
        worker.add_key(key=key)

    assert worker.component == case.expected_component
    assert worker.active is case.expected_active


def test_attribution_leaves_the_status_payload_unchanged() -> None:
    worker = WorkerInfo(identity="w1")
    worker.add_key(key="workers:active:git_agent:worker:w1")

    assert set(worker.to_dict()) == {"id", "active", "schema_hash"}
