"""Real-object builders for graph-traversal planner tests.

Constructs genuine ``SchemaBranch``, ``Branch``, and ``PermissionResolver``
instances rather than test doubles. ``PermissionResolver`` is the real class
used in production; its decision policy is driven by the permissions list the
caller supplies.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub.core.account import ObjectPermission
from infrahub.core.branch import Branch
from infrahub.core.schema import SchemaRoot
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.graph_traversal.planning.planner import SchemaPlanner
from infrahub.permissions.constants import PermissionDecisionFlag
from infrahub.permissions.resolver import PermissionResolver

if TYPE_CHECKING:
    from collections.abc import Iterable

    from infrahub.core.schema import GenericSchema, NodeSchema


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
