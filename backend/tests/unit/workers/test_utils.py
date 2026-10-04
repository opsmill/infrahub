from __future__ import annotations

from prefect import flow

from infrahub.workers.utils import with_opt_in_result_persistence


@flow(name="unit-flow-persistence-unset")
async def flow_persistence_unset() -> None:
    pass


@flow(name="unit-flow-persisting", persist_result=True)
async def flow_persisting() -> None:
    pass


@flow(name="unit-flow-not-persisting", persist_result=False)
async def flow_not_persisting() -> None:
    pass


def test_flow_leaving_persistence_unset_runs_without_persisting() -> None:
    flow_func = with_opt_in_result_persistence(flow_persistence_unset)

    assert flow_func.persist_result is False
    assert flow_func.name == "unit-flow-persistence-unset"
    assert flow_persistence_unset.persist_result is None


def test_flow_setting_persistence_is_returned_unchanged() -> None:
    assert with_opt_in_result_persistence(flow_persisting) is flow_persisting
    assert with_opt_in_result_persistence(flow_not_persisting) is flow_not_persisting


def test_the_same_flow_is_returned_on_every_call() -> None:
    assert with_opt_in_result_persistence(flow_persistence_unset) is with_opt_in_result_persistence(
        flow_persistence_unset
    )
