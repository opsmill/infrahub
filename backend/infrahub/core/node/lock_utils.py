import hashlib
from typing import TYPE_CHECKING

from infrahub.core.node import Node
from infrahub.core.schema import GenericSchema
from infrahub.core.schema.schema_branch import SchemaBranch

if TYPE_CHECKING:
    from infrahub.core.relationship import RelationshipManager


RESOURCE_POOL_LOCK_NAMESPACE = "resource_pool"


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


def _hash(value: str) -> str:
    # Do not use builtin `hash` for lock names as due to randomization results would differ between
    # different processes.
    return hashlib.sha256(value.encode()).hexdigest()


def get_lock_names_on_object_mutation(node: Node, schema_branch: SchemaBranch) -> list[str]:
    """
    Return lock names for object on which we want to avoid concurrent mutation (create/update).
    Lock names include kind, some generic kinds, resource pool ids, and values of attributes of corresponding uniqueness constraints.
    """

    lock_names: set[str] = set()

    # Check if node is using resource manager allocation via attributes
    for attr_name in node.get_schema().attribute_names:
        attribute = getattr(node, attr_name, None)
        if attribute is not None and getattr(attribute, "from_pool", None) and "id" in attribute.from_pool:
            lock_names.add(f"{RESOURCE_POOL_LOCK_NAMESPACE}.{attribute.from_pool['id']}")

    # Check if relationships allocate resources
    for rel_name in node._relationships:
        rel_manager: RelationshipManager = getattr(node, rel_name)
        for rel in rel_manager._relationships:
            if rel.from_pool and "id" in rel.from_pool:
                lock_names.add(f"{RESOURCE_POOL_LOCK_NAMESPACE}.{rel.from_pool['id']}")

    lock_kinds = _get_kinds_to_lock_on_object_mutation(node.get_kind(), schema_branch)
    for kind in lock_kinds:
        schema = schema_branch.get(name=kind, duplicate=False)
        ucs = schema.uniqueness_constraints
        if ucs is None:
            continue

        ucs_lock_names: list[str] = []
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
                attr = getattr(node, schema_path.attribute_schema.name, None)
                if attr is None or attr.value is None:
                    # `attr.value` being None corresponds to optional unique attribute.
                    # `attr` being None is not supposed to happen.
                    value_hashed = _hash("")
                else:
                    value_hashed = _hash(str(attr.value))

                uc_attributes_values.append(value_hashed)

            if uc_attributes_values:
                uc_lock_name = ".".join(uc_attributes_values)
                ucs_lock_names.append(uc_lock_name)

        if not ucs_lock_names:
            continue

        partial_lock_name = kind + "." + ".".join(ucs_lock_names)
        lock_names.add(build_object_lock_name(partial_lock_name))

    return sorted(lock_names)


def build_object_lock_name(name: str) -> str:
    return f"global.object.{name}"
