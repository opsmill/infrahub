from prefect import flow, task
from pydantic import BaseModel


class DummyInput(BaseModel):
    firstname: str
    lastname: str


class DummyOutput(BaseModel):
    full_name: str


@task
async def aggregate_name(firstname: str, lastname: str) -> str:
    return f"{firstname}, {lastname}"


@flow(persist_result=True)
async def dummy_flow(data: DummyInput) -> DummyOutput:
    return DummyOutput(full_name=await aggregate_name(firstname=data.firstname, lastname=data.lastname))
