"""Database and client sources behind the Python transform target resolver."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from infrahub import config
from infrahub.computed_attribute.gather import gather_python_transform_attributes
from infrahub.computed_attribute.read_sets import transform_read_set_from_query_report
from infrahub.core.query_group.subscribers import fetch_subscriber_refs
from infrahub.core.registry import registry
from infrahub.core.schema.schema_branch_computed import TransformReadSet
from infrahub.log import get_logger, get_run_logger
from infrahub.workers.dependencies import get_client, get_component
from infrahub.workflows.utils import wait_for_schema_to_converge

from .python_target_resolution import DisabledPythonTargetResolver, IndexedPythonTargetResolver, PythonAttributeReadSet

log = get_logger()

if TYPE_CHECKING:
    from infrahub_sdk.client import InfrahubClient

    from infrahub.core.query_group.subscribers import SubscriberRef
    from infrahub.database import InfrahubDatabase
    from infrahub.services import InfrahubComponent

    from .recompute_coalescing import PythonTargetResolver


@dataclass(frozen=True)
class DeclaredAttribute:
    """One Python transform computed attribute a branch's schema declares."""

    kind: str
    attribute_name: str


class DeclaredPythonAttributes(Protocol):
    """The Python transform computed attributes a branch's schema declares."""

    async def declared(self, *, branch: str) -> list[DeclaredAttribute]: ...


class AnalyzedPythonReadSets(Protocol):
    """The read set of every attribute whose transform query could be resolved and analyzed.

    An attribute missing from the result is one whose reads nothing established. Raises whatever the
    resolution raises, so the caller decides what a failure costs.
    """

    async def analyzed(self, *, branch: str) -> dict[DeclaredAttribute, TransformReadSet]: ...


class SchemaDeclaredPythonAttributes:
    """The declared attributes, read from the branch's schema once its workers agree on it."""

    def __init__(self, db: InfrahubDatabase, component: InfrahubComponent) -> None:
        self.db = db
        self.component = component

    async def declared(self, *, branch: str) -> list[DeclaredAttribute]:
        # A worker behind on the schema declares no Python attribute, which reads as nothing to do.
        await wait_for_schema_to_converge(
            branch_name=branch, component=self.component, db=self.db, log=get_run_logger()
        )
        if not registry.schema.has_schema_branch(name=branch):
            # The kinds of an unregistered branch are unknown, so there is nothing to widen to.
            # Every active branch is registered when the registry loads, so this stays unreached.
            log.warning("Skipping the Python computed attributes of %s: no schema is registered for it", branch)
            return []

        schema_branch = registry.schema.get_schema_branch(name=branch)
        return [
            DeclaredAttribute(kind=kind, attribute_name=attribute.name)
            for kind, attributes in schema_branch.computed_attributes.get_python_attributes_per_node().items()
            for attribute in attributes
        ]


class GatheredPythonReadSets:
    """The read sets, mapped from the transform queries the gather resolved and analyzed.

    A query whose root is not pinned to a single object gets no read set. Readers are resolved
    through query-group membership, which records what the last run read and never what the next one
    would: when any number of objects can answer the query, a node can enter or leave the result set
    while nothing changes on the nodes already in it, so a created node is invisible to the existing
    subscribers and a deleted one leaves no membership behind.

    The schema-change backfill maps the same queries without this restriction. It asks which
    attributes a changed schema element feeds and then refreshes whole kinds, so it never resolves a
    reader and cannot miss one.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def analyzed(self, *, branch: str) -> dict[DeclaredAttribute, TransformReadSet]:
        schema_branch = registry.schema.get_schema_branch(name=branch)
        gathered = await gather_python_transform_attributes(db=self.db, branch_name=branch)

        read_sets: dict[DeclaredAttribute, TransformReadSet] = {}
        for item in gathered:
            attribute = DeclaredAttribute(
                kind=item.computed_attribute.kind, attribute_name=item.computed_attribute.attribute.name
            )
            report = item.query_analyzer.query_report
            if not report.only_has_unique_targets:
                log.info(
                    "Widening the recompute of %s.%s: its transform query is not pinned to one object",
                    attribute.kind,
                    attribute.attribute_name,
                )
                read_sets[attribute] = TransformReadSet.imprecise()
                continue
            read_sets[attribute] = transform_read_set_from_query_report(report=report, schema_branch=schema_branch)
        return read_sets


class DatabasePythonReadSetSource:
    """Read sets for every Python transform computed attribute declared on a branch.

    The schema is what says which attributes exist; the analyzed transform queries are what says
    what each of them reads. Whatever the queries cannot supply, every attribute the schema declares
    still gets an entry, so the resolver widens it instead of skipping it. That holds for a single
    transform the gather did not find and for a gather that failed outright: it resolves its peers
    strictly, and one missing peer would otherwise take the whole pass down with it.
    """

    def __init__(self, declared_attributes: DeclaredPythonAttributes, read_sets: AnalyzedPythonReadSets) -> None:
        self.declared_attributes = declared_attributes
        self.read_sets_source = read_sets

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        declared = await self.declared_attributes.declared(branch=branch)
        if not declared:
            return []

        try:
            analyzed = await self.read_sets_source.analyzed(branch=branch)
        except Exception:
            log.exception("Widening every Python computed attribute on %s: the read-set gather failed", branch)
            analyzed = {}

        return [
            PythonAttributeReadSet(
                kind=attribute.kind,
                attribute_name=attribute.attribute_name,
                read_set=analyzed.get(attribute, TransformReadSet.imprecise()),
                gathered=attribute in analyzed,
            )
            for attribute in declared
        ]


class ClientSubscriberSource:
    """Query-group subscribers, read through the API client."""

    def __init__(self, client: InfrahubClient) -> None:
        self.client = client

    async def subscribers(self, *, node_ids: list[str], branch: str) -> list[SubscriberRef]:
        return await fetch_subscriber_refs(client=self.client, node_ids=node_ids, branch=branch)


async def build_python_target_resolver(*, db: InfrahubDatabase) -> PythonTargetResolver:
    """Build the resolver for one recompute pass, inert while the switch is off.

    The switch is read first, so a deployment that leaves the family to the per-node automations
    resolves neither the client nor the component.
    """
    if not config.SETTINGS.main.coalesce_python_recompute_after_merge:
        return DisabledPythonTargetResolver()

    return IndexedPythonTargetResolver(
        read_set_source=DatabasePythonReadSetSource(
            declared_attributes=SchemaDeclaredPythonAttributes(db=db, component=await get_component()),
            read_sets=GatheredPythonReadSets(db=db),
        ),
        subscriber_source=ClientSubscriberSource(client=get_client()),
    )
