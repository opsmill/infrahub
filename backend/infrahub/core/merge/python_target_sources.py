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
    from infrahub.core.schema import AttributeSchema
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


@dataclass(frozen=True)
class AnalyzedRead:
    """What one transform query reads, and whether its root is restricted to a single object."""

    read_set: TransformReadSet
    pinned: bool


class AnalyzedPythonReadSets(Protocol):
    """The read of every attribute whose transform query could be resolved and analyzed.

    An attribute missing from the result has no transform to compute it. Raises whatever the
    resolution raises, so the caller decides what a failure costs.
    """

    async def analyzed(self, *, branch: str) -> dict[DeclaredAttribute, AnalyzedRead]: ...


class SchemaDeclaredPythonAttributes:
    """The declared attributes, read from the branch's schema once its workers agree on it."""

    def __init__(self, db: InfrahubDatabase, component: InfrahubComponent) -> None:
        self.db = db
        self.component = component

    def _attributes_per_kind(self, *, branch: str) -> dict[str, list[AttributeSchema]]:
        return registry.schema.get_schema_branch(name=branch).computed_attributes.get_python_attributes_per_node()

    async def declared(self, *, branch: str) -> list[DeclaredAttribute]:
        if not registry.schema.has_schema_branch(name=branch):
            # The kinds of an unregistered branch are unknown, so there is nothing to widen to.
            # Every active branch is registered when the registry loads, so this stays unreached.
            log.warning("Skipping the Python computed attributes of %s: no schema is registered for it", branch)
            return []

        # Before the wait, which costs its full timeout whenever no worker publishes a schema hash.
        if not self._attributes_per_kind(branch=branch):
            return []

        # A worker behind on the schema declares no Python attribute, which reads as nothing to do.
        await wait_for_schema_to_converge(
            branch_name=branch, component=self.component, db=self.db, log=get_run_logger()
        )
        return [
            DeclaredAttribute(kind=kind, attribute_name=attribute.name)
            for kind, attributes in self._attributes_per_kind(branch=branch).items()
            for attribute in attributes
        ]


class GatheredPythonReadSets:
    """The reads, mapped from the transform queries the gather resolved and analyzed.

    Every query is mapped the same way the schema-scoped backfill maps it, so both sides scope a
    schema change on the same read set. A root that is not restricted to a single object is carried
    as a separate fact rather than folded into the mapping.
    """

    def __init__(self, db: InfrahubDatabase) -> None:
        self.db = db

    async def analyzed(self, *, branch: str) -> dict[DeclaredAttribute, AnalyzedRead]:
        schema_branch = registry.schema.get_schema_branch(name=branch)
        gathered = await gather_python_transform_attributes(db=self.db, branch_name=branch)

        reads: dict[DeclaredAttribute, AnalyzedRead] = {}
        for item in gathered:
            attribute = DeclaredAttribute(
                kind=item.computed_attribute.kind, attribute_name=item.computed_attribute.attribute.name
            )
            report = item.query_analyzer.query_report
            if not report.only_has_unique_targets:
                log.debug(
                    "Widening the recompute of %s.%s: its transform query is not pinned to one object",
                    attribute.kind,
                    attribute.attribute_name,
                )
            reads[attribute] = AnalyzedRead(
                read_set=transform_read_set_from_query_report(report=report, schema_branch=schema_branch),
                pinned=report.only_has_unique_targets,
            )
        return reads


class ComposedPythonReadSetSource:
    """Join what the schema declares with what the transform queries were found to read.

    The schema is what says which attributes exist; the analyzed queries are what says what each of
    them reads. An attribute the analysis returned nothing for has no transform to compute it, so it
    is left out: nothing can render its value until the transform arrives, and the recompute that
    follows the transform being created is what covers it then.

    An analysis that fails outright says nothing about any attribute, so every declared one is
    reported undeterminable and widens rather than dropping out unnoticed.
    """

    def __init__(self, declared_attributes: DeclaredPythonAttributes, analyzed_reads: AnalyzedPythonReadSets) -> None:
        self.declared_attributes = declared_attributes
        self.analyzed_reads = analyzed_reads

    async def read_sets(self, *, branch: str) -> list[PythonAttributeReadSet]:
        declared = await self.declared_attributes.declared(branch=branch)
        if not declared:
            return []

        try:
            analyzed = await self.analyzed_reads.analyzed(branch=branch)
        except Exception:
            log.exception("Widening every Python computed attribute on %s: the read-set gather failed", branch)
            return [
                PythonAttributeReadSet(
                    kind=attribute.kind,
                    attribute_name=attribute.attribute_name,
                    read_set=TransformReadSet.imprecise(),
                    gathered=False,
                )
                for attribute in declared
            ]

        return [
            PythonAttributeReadSet(
                kind=attribute.kind,
                attribute_name=attribute.attribute_name,
                read_set=analyzed[attribute].read_set,
                pinned=analyzed[attribute].pinned,
            )
            for attribute in declared
            if attribute in analyzed
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
        log.debug("Deriving no Python computed attribute for this pass: the coalesced pass is disabled")
        return DisabledPythonTargetResolver()

    return IndexedPythonTargetResolver(
        read_set_source=ComposedPythonReadSetSource(
            declared_attributes=SchemaDeclaredPythonAttributes(db=db, component=await get_component()),
            analyzed_reads=GatheredPythonReadSets(db=db),
        ),
        subscriber_source=ClientSubscriberSource(client=get_client()),
    )
