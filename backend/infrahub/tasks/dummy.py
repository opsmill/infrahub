from __future__ import annotations

import logging

from prefect import flow, task
from pydantic import BaseModel

from infrahub.workflows.models import WorkflowDefinition


class DummyInput(BaseModel):
    firstname: str
    lastname: str


class DummyOutput(BaseModel):
    full_name: str


DUMMY_FLOW = WorkflowDefinition(
    name="dummy_flow",
    module="infrahub.tasks.dummy",
    function="dummy_flow",
)

DUMMY_FLOW_BROKEN = WorkflowDefinition(
    name="dummy_flow_broken",
    module="infrahub.tasks.dummy",
    function="dummy_flow_broken",
)


@task
async def aggregate_name(firstname: str, lastname: str) -> str:
    return f"{firstname}, {lastname}"


@flow(name="dummy-flow", persist_result=True)
async def dummy_flow(data: DummyInput) -> DummyOutput:
    logging.getLogger("infrahub.tasks").info("Log in the flow")
    return DummyOutput(full_name=await aggregate_name(firstname=data.firstname, lastname=data.lastname))


@flow(name="dummy-flow-broken", persist_result=True)
async def dummy_flow_broken(data: DummyInput) -> DummyOutput:
    response = await aggregate_name(firstname=data.firstname, lastname=data.lastname)
    return DummyOutput(not_valid=response)  # type: ignore[call-arg]
