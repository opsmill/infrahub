from infrahub.core.branch import Branch
from infrahub.core.constants import InfrahubKind
from infrahub.core.node import Node
from infrahub.core.schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch
from infrahub.lock import build_object_lock_name

KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED = [InfrahubKind.GENERICGROUP]


def _get_kinds_to_lock_on_object_mutation(kind: str, schema_branch: SchemaBranch) -> list[str]:
    """
    Return kinds for which we want to lock during creating / updating an object of a given schema node.
    Lock should be performed on schema kind and its generics having a uniqueness_constraint defined.
    If a generic uniqueness constraint is the same as the node schema one,
    it means node schema overrided this constraint, in which case we only need to lock on the generic.
    """

    node_schema = schema_branch.get(name=kind)

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
        generic_uc = schema_branch.get(name=generic_kind).uniqueness_constraints
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

    node_schema = schema_branch.get(name=kind)
    if isinstance(node_schema, GenericSchema):
        return False

    for generic_kind in node_schema.inherit_from:
        if generic_kind in KINDS_CONCURRENT_MUTATIONS_NOT_ALLOWED:
            return True
    return False


def get_lock_names_on_object_mutation(node: Node, branch: Branch, schema_branch: SchemaBranch) -> list[str]:
    """
    Return lock names for object on which we want to avoid concurrent mutation (create/update). Except for some specific kinds,
    concurrent mutations are only allowed on non-main branch as objects validations will be performed at least when merging in main branch.
    Lock names include kind, some generic kinds, and values of attributes of corresponding uniqueness constraints.
    """

    if not branch.is_default and not _should_kind_be_locked_on_any_branch(node.get_kind(), schema_branch):
        return []

    lock_kinds = _get_kinds_to_lock_on_object_mutation(node.get_kind(), schema_branch)
    lock_names = []
    for kind in lock_kinds:
        schema = schema_branch.get(name=kind)
        ucs = schema.uniqueness_constraints
        if ucs is None:
            continue

        ucs_lock_names = []
        uc_attributes_names = set()

        for uc in ucs:
            uc_attributes_values = []
            # Keep only attributes constraints
            for field_path in uc:
                # Some attributes may exist in different uniqueness constraints, we de-duplicate them
                if field_path in uc_attributes_names:
                    continue

                # Exclude relationships uniqueness constraints
                schema_path = schema.parse_schema_path(path=field_path, schema=schema_branch)
                if schema_path.related_schema is not None or schema_path.attribute_schema is None:
                    continue

                uc_attributes_names.add(field_path)
                value_hashed = str(hash(str(getattr(node, schema_path.attribute_schema.name).value)))
                uc_attributes_values.append(value_hashed)

            if uc_attributes_values:
                uc_lock_name = ".".join(uc_attributes_values)
                ucs_lock_names.append(uc_lock_name)

        partial_lock_name = kind + "." + ".".join(ucs_lock_names)
        lock_names.append(build_object_lock_name(partial_lock_name))

    return lock_names
