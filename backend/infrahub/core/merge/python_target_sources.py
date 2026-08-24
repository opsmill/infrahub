"""Database and client sources behind the Python transform target resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub import config
from infrahub.computed_attribute.gather import gather_python_transform_attributes
from infrahub.computed_attribute.read_sets import transform_read_set_from_query_report
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch_computed import TransformReadSet

from .python_target_resolution import PythonAttributeReadSet, PythonTargetResolver

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.query_group.subscribers import SubscriberRef
    from infrahub.database import InfrahubDatabase


class DatabasePythonReadSetSource:
    """Read sets for every Python transform computed attribute declared on a branch.

    The schema is what says which attributes exist; the analyzed transform queries are what says
    what each of them reads. An attribute the gather could not resolve keeps an imprecise read set
    rather than disappearing, so the resolver widens it instead of skipping it.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        schema_branch = registry.schema.get_schema_branch(name=branch)
        gathered = await gather_python_transform_attributes(db=self.db, branch_name=branch)
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
            for kind, attributes in schema_branch.computed_attributes.get_python_attributes_per_node().items()
            for attribute in attributes
        ]


class ClientSubscriberSource:
    """Query-group subscribers, read through the API client."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        return await fetch_subscriber_refs(client=self.client, node_ids=node_ids, branch=branch)


def build_python_target_resolver(
    *, db: InfrahubDatabase, client: InfrahubClient, branch: str
) -> PythonTargetResolver | None:
    """Build the resolver for one merge or rebase pass, or None while the switch is off."""
    if not config.SETTINGS.main.coalesce_python_recompute_after_merge:
        return None

    return PythonTargetResolver(
        read_set_source=DatabasePythonReadSetSource(db=db),
        subscriber_source=ClientSubscriberSource(client=client),
        branch=branch,
    )
