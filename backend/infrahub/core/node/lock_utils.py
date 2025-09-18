import hashlib
from typing import Any

from infrahub.core.branch import Branch
from infrahub.core.constants.infrahubkind import GENERICGROUP, GRAPHQLQUERYGROUP
from infrahub.core.schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch

KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED = [GENERICGROUP]


def _get_kinds_to_lock_on_object_mutation(kind: str, schema_branch: SchemaBranch) -> list[str]:
    """
    Return kinds for which we want to lock during creating / updating an object of a given schema node.
    Lock should be performed on schema kind and its generics having a uniqueness_constraint defined.
    If a generic uniqueness constraint is the same as the node schema one,
    it means node schema overrided this constraint, in which case we only need to lock on the generic.
    """

    node_schema = schema_branch.get(name=kind, duplicate=False)

    schema_uc = None
    kinds = []
    if node_schema.uniqueness_constraints:
        kinds.append(node_schema.kind)
        schema_uc = node_schema.uniqueness_constraints

    if isinstance(node_schema, GenericSchema):
        return kinds

    generics_kinds = node_schema.inherit_from

    node_schema_kind_removed = False
    for generic_kind in generics_kinds:
        generic_uc = schema_branch.get(name=generic_kind, duplicate=False).uniqueness_constraints
        if generic_uc:
            kinds.append(generic_kind)
            if not node_schema_kind_removed and generic_uc == schema_uc:
                # Check whether we should remove original schema kind as it simply overrides uniqueness_constraint
                # of a generic
                kinds.pop(0)
                node_schema_kind_removed = True
    return kinds


def _should_kind_be_locked_on_any_branch(kind: str, schema_branch: SchemaBranch) -> bool:
    """
    Check whether kind or any kind generic is in KINDS_TO_LOCK_ON_ANY_BRANCH.
    """

    if kind in KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED:
        return True

    node_schema = schema_branch.get(name=kind, duplicate=False)
    if isinstance(node_schema, GenericSchema):
        return False

    for generic_kind in node_schema.inherit_from:
        if generic_kind in KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED:
            return True
    return False


def _hash(value: str) -> str:
    # Do not use builtin `hash` for lock names as due to randomization results would differ between
    # different processes.
    return hashlib.sha256(value.encode()).hexdigest()


def get_kind_lock_names_on_object_mutation(
    kind: str, branch: Branch, schema_branch: SchemaBranch, data: dict[str, Any]
) -> list[str]:
    """
    Return objects kind for which we want to avoid concurrent mutation (create/update). Except for some specific kinds,
    concurrent mutations are only allowed on non-main branch as objects validations will be performed at least when merging in main branch.
    """

    if not branch.is_default and not _should_kind_be_locked_on_any_branch(kind=kind, schema_branch=schema_branch):
        return []

    if kind == GRAPHQLQUERYGROUP:
        # Lock on name as well to improve performances
        try:
            name = data["name"].value
            return [build_object_lock_name(kind + "." + _hash(name))]
        except KeyError:
            # We might reach here if we are updating a CoreGraphQLQueryGroup without updating the name,
            # in which case we would not need to lock. This is not supposed to happen as current `update`
            # logic first fetches the node with its name.
            return []

    lock_kinds = _get_kinds_to_lock_on_object_mutation(kind, schema_branch)
    lock_names = [build_object_lock_name(kind) for kind in lock_kinds]
    return lock_names


def build_object_lock_name(name: str) -> str:
    return f"global.object.{name}"
