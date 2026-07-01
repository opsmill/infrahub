"""Real-object builders for graph-traversal planner tests.

Constructs genuine ``SchemaBranch``, ``Branch``, and ``PermissionResolver``
instances rather than test doubles. ``PermissionResolver`` is the real class
used in production; its decision policy is driven by the permissions list the
caller supplies.
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, NamedTuple

from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.exceptions import QueryTimeoutError
from infrahub.graph_traversal._cypher import GraphTraversalCypherRenderer
from infrahub.graph_traversal.executor import (
    DEFAULT_EXHAUSTIVE_HALF_CAP,
    PathTraversalExecutor,
    ReachableNodesExecutor,
)
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.graph_traversal.runner import DefaultQueryRunner, QueryRunner
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.node import Node
    from infrahub.core.query import Query
    from infrahub.core.schema import GenericSchema, NodeSchema
    from infrahub.database import InfrahubDatabase
    from infrahub.graph_traversal.planning.models import Plan


class TimeoutOnNthQuery:
    """Test ``QueryRunner`` that simulates a server timeout on the ``nth`` query of a given name.

    Every other query runs against the database normally, so a test can let shallow tiers complete
    and force a single deeper query to time out — exercising the executor's truncation path without
    a real timeout and without mocking.
    """

    def __init__(self, *, name: str, nth: int) -> None:
        self._name = name
        self._nth = nth
        self._seen = 0

    async def run(self, query: Query, *, db: InfrahubDatabase, timeout_seconds: float | None) -> None:
        if query.name == self._name:
            self._seen += 1
            if self._seen == self._nth:
                raise QueryTimeoutError(message=f"simulated timeout on {self._name} #{self._nth}")
        await query.execute(db=db, timeout_seconds=timeout_seconds)


class CountingQueryRunner:
    """Test ``QueryRunner`` that records how many times each query name was executed."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = defaultdict(int)

    async def run(self, query: Query, *, db: InfrahubDatabase, timeout_seconds: float | None) -> None:
        self.counts[query.name] += 1
        await query.execute(db=db, timeout_seconds=timeout_seconds)


class ShortcutGraph(NamedTuple):
    """Vertices of the non-bipartite ``linked_vertices_with_shortcut`` fixture.

    Edges: ``source-middle`` (a shortcut) and ``source-detour-middle``, plus
    ``middle-bridge-destination`` — so the middle is reachable from the source both by its
    shortest route (direct) and by a longer one, and the longer ``source-detour-middle-bridge-
    destination`` path's midpoint is not at its shortest distance.
    """

    source: Node
    detour: Node
    middle: Node
    bridge: Node
    destination: Node


def dump_adjacency(plan: Plan) -> dict[str, dict[str, frozenset[str]]]:
    """Reconstruct the adjacency shape for test assertions via the plan's public accessors."""
    return {
        kind: {rel_name: frozenset(ends) for rel_name, ends in plan.get_relationship_map_for_kind(kind).items()}
        for kind in plan.get_all_source_kinds()
    }


def identifier_of(*, db: InfrahubDatabase, branch: Branch, kind: str, relationship: str) -> str:
    """Look up a schema relationship's identifier on the live branch view."""
    schema_branch = db.schema.get_schema_branch(name=branch.name)
    return schema_branch.get_node(name=kind, duplicate=False).get_relationship(name=relationship).get_identifier()


def build_schema_branch(
    *,
    nodes: Iterable[NodeSchema] = (),
    generics: Iterable[GenericSchema] = (),
    name: str = "test",
    disable_profile_generation: bool = True,
) -> SchemaBranch:
    """Build and process a SchemaBranch from explicit node + generic schemas.

    Calls ``load_schema`` + ``process(validate_schema=False)`` so that
    ``RelationshipSchema.identifier`` is auto-generated, generic ``used_by``
    is populated, and inheritance is resolved — without requiring core models.

    By default ``generate_profile`` is forced to ``False`` on every supplied
    node so the planner's route enumeration isn't polluted by the
    ``ProfileTesting*`` schemas that ``process_post_validation`` would
    otherwise auto-attach to each concrete kind. Tests that need to exercise
    profile behavior can pass ``disable_profile_generation=False``.
    """
    node_list = list(nodes)
    if disable_profile_generation:
        for node in node_list:
            node.generate_profile = False
    schema_branch = SchemaBranch(cache={}, name=name)
    schema_branch.load_schema(schema=SchemaRoot(nodes=node_list, generics=list(generics)))
    schema_branch.process(validate_schema=False)
    return schema_branch


def build_permission_resolver(
    *,
    denied_kinds: set[str] | None = None,
    default_branch_name: str = "main",
) -> PermissionResolver:
    """Build a real ``PermissionResolver`` with a wildcard-allow / per-kind-deny policy.

    With ``denied_kinds=None`` (the default), every kind is permitted via a
    single wildcard ``ObjectPermission(namespace="*", name="*", action="view",
    decision=ALLOW_ALL)``. For each kind in ``denied_kinds``, an additional
    higher-specificity ``DENY`` permission is appended; the resolver's
    specificity ranking ensures the kind-specific deny wins over the wildcard
    allow.
    """
    denied_kinds = denied_kinds or set()
    object_permissions: list[ObjectPermission] = [
        ObjectPermission(
            namespace="*",
            name="*",
            action="view",
            decision=PermissionDecisionFlag.ALLOW_ALL.value,
        ),
    ]
    object_permissions.extend(
        ObjectPermission(
            namespace="*",
            name=kind,
            action="view",
            decision=PermissionDecisionFlag.DENY.value,
        )
        for kind in sorted(denied_kinds)
    )
    return PermissionResolver(
        permissions={"global_permissions": [], "object_permissions": object_permissions},
        default_branch_name=default_branch_name,
    )


def build_reachable_executor(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    default_branch_name: str,
) -> ReachableNodesExecutor:
    """Construct a ``GraphTraversalCypherRenderer`` and a ``ReachableNodesExecutor`` around it."""
    renderer = GraphTraversalCypherRenderer(
        branch=branch,
        default_branch_name=default_branch_name,
    )
    return ReachableNodesExecutor(db=db, branch=branch, renderer=renderer)


def build_path_traversal_executor(
    *,
    db: InfrahubDatabase,
    branch: Branch,
    default_branch_name: str,
    exhaustive_half_cap: int = DEFAULT_EXHAUSTIVE_HALF_CAP,
    query_runner: QueryRunner | None = None,
) -> PathTraversalExecutor:
    """Construct a ``GraphTraversalCypherRenderer`` and a ``PathTraversalExecutor`` around it."""
    renderer = GraphTraversalCypherRenderer(
        branch=branch,
        default_branch_name=default_branch_name,
    )
    return PathTraversalExecutor(
        db=db,
        branch=branch,
        renderer=renderer,
        query_runner=query_runner or DefaultQueryRunner(),
        exhaustive_half_cap=exhaustive_half_cap,
    )


def make_planner(
    *,
    schema_branch: SchemaBranch,
    branch: Branch | None = None,
    permission_resolver: PermissionResolver | None = None,
    denied_kinds: set[str] | None = None,
    default_branch_name: str = "main",
) -> SchemaPlanner:
    """Build a SchemaPlanner against real schema/branch/resolver objects.

    ``denied_kinds`` is a shortcut: when set, a real ``PermissionResolver``
    that allows everything except those kinds is constructed automatically.
    Callers that need a more elaborate permission policy should pass
    ``permission_resolver`` directly.
    """
    if branch is None:
        branch = Branch(name=default_branch_name)
        branch.is_default = True
    if permission_resolver is None:
        permission_resolver = build_permission_resolver(
            denied_kinds=denied_kinds,
            default_branch_name=default_branch_name,
        )
    return SchemaPlanner(
        schema_branch=schema_branch,
        branch=branch,
        permission_resolver=permission_resolver,
    )
