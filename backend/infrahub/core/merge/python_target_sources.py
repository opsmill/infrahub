"""Database and client sources behind the Python transform target resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.computed_attribute.gather import gather_python_transform_attributes
from infrahub.computed_attribute.read_sets import transform_read_set_from_query_report
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.log import get_logger, get_run_logger
from infrahub.workers.dependencies import get_client, get_component
from infrahub.workflows.utils import wait_for_schema_to_converge

from .python_target_resolution import PythonAttributeReadSet, PythonTargetResolver
from .recompute_coalescing import DisabledPythonTargetDeriver, PythonTargetDeriver

log = get_logger()

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.query_group.subscribers import SubscriberRef
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubComponent


class DatabasePythonReadSetSource:
    """Read sets for every Python transform computed attribute declared on a branch.

    The schema is what says which attributes exist; the analyzed transform queries are what says
    what each of them reads. Whatever the queries cannot supply, every attribute the schema declares
    still gets an entry, so the resolver widens it instead of skipping it. That holds for a single
    transform the gather did not find and for a gather that failed outright: it resolves its peers
    strictly, and one missing peer would otherwise take the whole pass down with it.
    """

    def __init__(self, db: InfrahubDatabase, component: InfrahubComponent) -> None:
        self.db = db
        self.component = component

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        # A worker still behind on the schema declares no Python attribute at all, and an empty
        # index reads exactly like a branch with nothing to refresh.
        await wait_for_schema_to_converge(
            branch_name=branch, component=self.component, db=self.db, log=get_run_logger()
        )
        schema_branch = registry.schema.get_schema_branch(name=branch)
        attributes_per_kind = schema_branch.computed_attributes.get_python_attributes_per_node()
        if not attributes_per_kind:
            return []

        try:
            gathered = await gather_python_transform_attributes(db=self.db, branch_name=branch)
        except Exception:
            log.exception("Widening every Python computed attribute on %s: the read-set gather failed", branch)
            gathered = []
        analyzed = {
            (
                item.computed_attribute.kind,
                item.computed_attribute.attribute.name,
            ): transform_read_set_from_query_report(
                report=item.query_analyzer.query_report, schema_branch=schema_branch
            )
            for item in gathered
        }
        return [
            PythonAttributeReadSet(
                kind=kind,
                attribute_name=attribute.name,
                read_set=analyzed.get((kind, attribute.name), TransformReadSet.imprecise()),
            )
            for kind, attributes in attributes_per_kind.items()
            for attribute in attributes
        ]


class ClientSubscriberSource:
    """Query-group subscribers, read through the API client."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        return await fetch_subscriber_refs(client=self.client, node_ids=node_ids, branch=branch)


async def build_python_target_deriver(*, db: InfrahubDatabase) -> PythonTargetDeriver:
    """Build the derivation for one recompute pass, inert while the switch is off.

    The switch is read before anything else is resolved: a deployment that leaves the family to the
    per-node automations must not pay for the client and the component, nor be able to fail on them.
    """
    if not config.SETTINGS.main.coalesce_python_recompute_after_merge:
        return DisabledPythonTargetDeriver()

    return PythonTargetResolver(
        read_set_source=DatabasePythonReadSetSource(db=db, component=await get_component()),
        subscriber_source=ClientSubscriberSource(client=get_client()),
    )
