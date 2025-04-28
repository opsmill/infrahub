from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from infrahub_sdk.utils import compare_lists, deep_merge_dict, duplicates, intersection
from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

from infrahub.core.constants import (
    HashableModelState,
    SchemaPathType,
    UpdateSupport,
    UpdateValidationErrorType,
)
from infrahub.core.path import SchemaPath

if TYPE_CHECKING:
    from infrahub.core.schema import MainSchemaTypes
    from infrahub.core.schema.schema_branch import SchemaBranch

GENERIC_ATTRIBUTES_TO_IGNORE = ["namespace", "name", "branch"]


class NodeKind(BaseModel):
    namespace: str
    name: str

    def __str__(self) -> str:
        return f"{self.namespace}{self.name}"


class SchemaBranchDiff(BaseModel):
    added_nodes: list[str] = Field(default_factory=list)
    changed_nodes: list[str] = Field(default_factory=list)
    added_generics: list[str] = Field(default_factory=list)
    changed_generics: list[str] = Field(default_factory=list)
    removed_nodes: list[str] = Field(default_factory=list)
    removed_generics: list[str] = Field(default_factory=list)

    def to_string(self) -> str:
        return ", ".join(self.nodes + self.generics)

    def to_list(self) -> list[str]:
        return self.nodes + self.generics

    @property
    def has_diff(self) -> bool:
        return any([self.has_node_diff, self.has_generic_diff])

    @property
    def has_node_diff(self) -> bool:
        return bool(self.added_nodes + self.changed_nodes + self.removed_nodes)

    @property
    def has_generic_diff(self) -> bool:
        return bool(self.added_generics + self.changed_generics + self.removed_generics)

    @property
    def nodes(self) -> list[str]:
        """Return nodes that are still active."""
        return self.added_nodes + self.changed_nodes

    @property
    def generics(self) -> list[str]:
        """Return generics that are still active."""
        return self.added_generics + self.changed_generics


class SchemaBranchHash(BaseModel):
    main: str
    nodes: dict[str, str] = Field(default_factory=dict)
    generics: dict[str, str] = Field(default_factory=dict)

    def compare(self, other: SchemaBranchHash) -> SchemaBranchDiff | None:
        if other.main == self.main:
            return None

        return SchemaBranchDiff(
            added_nodes=[key for key in other.nodes if key not in self.nodes],
            changed_nodes=[key for key, value in other.nodes.items() if key in self.nodes and self.nodes[key] != value],
            removed_nodes=[key for key in self.nodes if key not in other.nodes],
            added_generics=[key for key in other.generics if key not in self.generics],
            changed_generics=[
                key for key, value in other.generics.items() if key in self.generics and self.generics[key] != value
            ],
            removed_generics=[key for key in self.generics if key not in other.generics],
        )


class SchemaDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added: dict[str, HashableModelDiff] = Field(default_factory=dict)
    changed: dict[str, HashableModelDiff] = Field(default_factory=dict)
    removed: dict[str, HashableModelDiff] = Field(default_factory=dict)

    @property
    def all(self) -> list[str]:
        return list(self.changed.keys()) + list(self.added.keys()) + list(self.removed.keys())

    def __add__(self, other: SchemaDiff) -> SchemaDiff:
        merged_dict = deep_merge_dict(self.model_dump(), other.model_dump())
        return self.__class__(**merged_dict)

    def print(self, indentation: int = 4, column_size: int = 32) -> None:
        data = self.model_dump()

        indent_str = " " * indentation

        for node_action, node_info in data.items():
            for node_name, elements in node_info.items():
                print(f"{str(node_name).ljust(column_size)} | {str(node_action).title()}")
                for element_action, element_info in elements.items():
                    for element_name, element_children in element_info.items():
                        print(
                            f"{indent_str}{str(element_name).ljust(column_size - indentation)} | {str(element_action).title()}"
                        )
                        if element_children and isinstance(element_children, dict):
                            for sub_action, sub_info in element_children.items():
                                for sub_name in sub_info.keys():
                                    print(
                                        f"{indent_str * 2}{str(sub_name).ljust(column_size - indentation * 2)} | {str(sub_action).title()}"
                                    )


class SchemaUpdateValidationError(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    error: UpdateValidationErrorType
    message: str | None = None

    def to_string(self) -> str:
        return f"{self.error.value!r}: {self.path.schema_kind} {self.path.field_name} {self.message}"


class SchemaUpdateMigrationInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    migration_name: str

    @property
    def routing_key(self) -> str:
        return "schema.migration.path"


class SchemaUpdateConstraintInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: SchemaPath
    constraint_name: str

    @property
    def routing_key(self) -> str:
        return "schema.validator.path"

    def __hash__(self) -> int:
        return hash((type(self),) + tuple(self.constraint_name + self.path.get_path()))


class SchemaUpdateValidationResult(BaseModel):
    errors: list[SchemaUpdateValidationError] = Field(default_factory=list)
    constraints: list[SchemaUpdateConstraintInfo] = Field(default_factory=list)
    migrations: list[SchemaUpdateMigrationInfo] = Field(default_factory=list)
    enforce_update_support: bool = True
    diff: SchemaDiff

    @classmethod
    def init(cls, diff: SchemaDiff, schema: SchemaBranch, enforce_update_support: bool = True) -> Self:
        obj = cls(diff=diff, enforce_update_support=enforce_update_support)
        obj.process_diff(schema=schema)

        return obj

    def process_diff(self, schema: SchemaBranch) -> None:
        for schema_name in self.diff.removed.keys():
            self.migrations.append(
                SchemaUpdateMigrationInfo(
                    path=SchemaPath(  # type: ignore[call-arg]
                        schema_kind=schema_name, path_type=SchemaPathType.NODE
                    ),
                    migration_name="node.remove",
                )
            )

        for schema_name, schema_diff in self.diff.changed.items():
            schema_node = schema.get(name=schema_name, duplicate=False)
            if "inherit_from" in schema_diff.changed:
                self.migrations.append(
                    SchemaUpdateMigrationInfo(
                        path=SchemaPath(  # type: ignore[call-arg]
                            schema_kind=schema_name, path_type=SchemaPathType.NODE
                        ),
                        migration_name="node.inherit_from.update",
                    )
                )

            # Nothing to do today if we add a new attribute to a node in the schema
            # for node_field_name, _ in schema_diff.added.items():
            #     pass

            # Not possible today, removing an attribute from the schema will be manage by database migrations
            # for node_field_name, _ in schema_diff.removed.items():
            #     pass

            for node_field_name, node_field_diff in schema_diff.changed.items():
                if node_field_diff and node_field_name in ["attributes", "relationships"]:
                    self._process_attrs_rels(
                        schema=schema_node, node_field_name=node_field_name, node_field_diff=node_field_diff
                    )
                else:
                    self._process_node_attributes(schema=schema_node, node_field_name=node_field_name)

    def _process_attrs_rels(
        self,
        schema: MainSchemaTypes,
        node_field_name: str,
        node_field_diff: HashableModelDiff,
    ) -> None:
        path_type = SchemaPathType.ATTRIBUTE if node_field_name == "attributes" else SchemaPathType.RELATIONSHIP
        for field_name in node_field_diff.added.keys():
            if path_type == SchemaPathType.ATTRIBUTE:
                self.migrations.append(
                    SchemaUpdateMigrationInfo(
                        path=SchemaPath(  # type: ignore[call-arg]
                            schema_kind=schema.kind, path_type=path_type, field_name=field_name
                        ),
                        migration_name="node.attribute.add",
                    )
                )
            elif path_type == SchemaPathType.RELATIONSHIP:
                self.constraints.append(
                    SchemaUpdateConstraintInfo(
                        path=SchemaPath(  # type: ignore[call-arg]
                            schema_kind=schema.kind, path_type=path_type, field_name=field_name
                        ),
                        constraint_name="node.relationship.add",
                    )
                )

        for field_name in node_field_diff.removed.keys():
            self.migrations.append(
                SchemaUpdateMigrationInfo(  # type: ignore[call-arg]
                    path=SchemaPath(  # type: ignore[call-arg]
                        schema_kind=schema.kind, path_type=path_type, field_name=field_name
                    ),
                    migration_name=f"node.{path_type.value}.remove",
                )
            )

        for field_name, sub_field_diff in node_field_diff.changed.items():
            field = schema.get_field(name=field_name)

            if not sub_field_diff:
                raise ValueError("sub_field_diff must be defined, unexpected situation")

            for prop_name in sub_field_diff.changed:
                field_info = field.model_fields[prop_name]
                field_update = str(field_info.json_schema_extra.get("update"))  # type: ignore[union-attr]

                schema_path = SchemaPath(  # type: ignore[call-arg]
                    schema_kind=schema.kind,
                    path_type=path_type,
                    field_name=field_name,
                    property_name=prop_name,
                )

                self._process_field(
                    schema_path=schema_path,
                    field_update=field_update,
                )

    def _process_node_attributes(self, schema: MainSchemaTypes, node_field_name: str) -> None:
        field_info = schema.model_fields[node_field_name]
        field_update = str(field_info.json_schema_extra.get("update"))  # type: ignore[union-attr]

        # No need to execute a migration for generic nodes attributes because they are not stored in the database
        if schema.is_generic_schema and node_field_name in GENERIC_ATTRIBUTES_TO_IGNORE:
            return

        schema_path = SchemaPath(  # type: ignore[call-arg]
            schema_kind=schema.kind,
            path_type=SchemaPathType.NODE,
            field_name=node_field_name,
            property_name=node_field_name,
        )
        self._process_field(
            schema_path=schema_path,
            field_update=field_update,
        )

    def _process_field(
        self,
        schema_path: SchemaPath,
        field_update: str,
    ) -> None:
        if field_update == UpdateSupport.NOT_SUPPORTED.value and self.enforce_update_support:
            self.errors.append(
                SchemaUpdateValidationError(
                    path=schema_path,
                    error=UpdateValidationErrorType.NOT_SUPPORTED,
                )
            )
        elif field_update == UpdateSupport.MIGRATION_REQUIRED.value:
            migration_name = f"{schema_path.path_type.value}.{schema_path.property_name}.update"
            self.migrations.append(
                SchemaUpdateMigrationInfo(
                    path=schema_path,
                    migration_name=migration_name,
                )
            )
        elif field_update == UpdateSupport.VALIDATE_CONSTRAINT.value:
            constraint_name = f"{schema_path.path_type.value}.{schema_path.property_name}.update"
            self.constraints.append(
                SchemaUpdateConstraintInfo(
                    path=schema_path,
                    constraint_name=constraint_name,
                )
            )

    def validate_all(self, migration_map: dict[str, Any], validator_map: dict[str, Any]) -> None:
        self.validate_migrations(migration_map=migration_map)
        self.validate_constraints(validator_map=validator_map)
        self.add_validator_for_migration(validator_map=validator_map)

    def validate_migrations(self, migration_map: dict[str, Any]) -> None:
        for migration in self.migrations:
            if migration_map.get(migration.migration_name, None) is None:
                self.errors.append(
                    SchemaUpdateValidationError(
                        path=migration.path,
                        error=UpdateValidationErrorType.MIGRATION_NOT_AVAILABLE,
                        message=f"Migration {migration.migration_name!r} is not available yet",
                    )
                )

    def validate_constraints(self, validator_map: dict[str, Any]) -> None:
        for constraint in self.constraints:
            if validator_map.get(constraint.constraint_name, None) is None:
                self.errors.append(
                    SchemaUpdateValidationError(
                        path=constraint.path,
                        error=UpdateValidationErrorType.VALIDATOR_NOT_AVAILABLE,
                        message=f"Validator {constraint.constraint_name!r} is not available yet",
                    )
                )

    def add_validator_for_migration(self, validator_map: dict[str, Any]) -> None:
        for migration in self.migrations:
            if validator_map.get(migration.migration_name):
                self.constraints.append(
                    SchemaUpdateConstraintInfo(
                        path=migration.path,
                        constraint_name=migration.migration_name,
                    )
                )


class HashableModelDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")
    added: dict[str, HashableModelDiff | None] = Field(default_factory=dict)
    changed: dict[str, HashableModelDiff | None] = Field(default_factory=dict)
    removed: dict[str, HashableModelDiff | None] = Field(default_factory=dict)

    @property
    def has_diff(self) -> bool:
        return bool(len(self.added) + len(self.changed) + len(self.removed))


class HashableModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    state: HashableModelState = HashableModelState.PRESENT

    _exclude_from_hash: list[str] = []
    _sort_by: list[str] = []

    def __hash__(self) -> int:
        return hash(self.get_hash())

    def get_hash(self, display_values: bool = False) -> str:
        """Generate a hash for the object.

        Calculating a hash can be very complicated if the data that we are storing is dynamic
        In order for this function to work, it's recommended to exclude all objects or list of objects with _exclude_from_hash
        List of hashable elements are fine and they will be converted automatically to Tuple.
        """

        values = []
        md5hash = hashlib.md5(usedforsecurity=False)
        for field_name in sorted(self.model_fields.keys()):
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            value = getattr(self, field_name)
            signatures = self._get_signature_field(value)
            for item in signatures:
                values.append(item)
                md5hash.update(item)

        if display_values:
            from rich import print as rprint

            rprint(tuple(values))

        return md5hash.hexdigest()

    @classmethod
    def _get_hash_value(cls, value: Any) -> bytes:
        if hasattr(value, "get_hash"):
            return value.get_hash().encode()

        return str(value).encode()

    @classmethod
    def _get_signature_field(cls, value: Any) -> list[bytes]:
        hashes: list[bytes] = []
        if isinstance(value, list):
            for item in sorted(value):
                hashes.append(cls._get_hash_value(item))
        elif isinstance(value, dict):
            for key, content in frozenset(sorted(value.items())):
                hashes.append(cls._get_hash_value(key))
                hashes.append(cls._get_hash_value(content))
        else:
            hashes.append(cls._get_hash_value(value))

        return sorted(hashes)

    @property
    def _sorting_id(self) -> tuple[Any]:
        return tuple(getattr(self, key) for key in self._sort_by if hasattr(self, key))

    def _sorting_keys(self, other: HashableModel) -> tuple[list[Any], list[Any]]:
        """Retrieve the values of the attributes listed in the _sort_key list, for both objects."""
        if not self._sort_by:
            raise TypeError(f"Sorting not supported for instance of {self.__class__.__name__}")

        if not hasattr(other, "_sort_by") and not other._sort_by:
            raise TypeError(
                f"Sorting not supported between instance of {other.__class__.__name__} and {self.__class__.__name__}"
            )

        self_sort_keys: list[Any] = [getattr(self, key) for key in self._sort_by if hasattr(self, key)]
        other_sort_keys: list[Any] = [getattr(other, key) for key in other._sort_by if hasattr(other, key)]

        return self_sort_keys, other_sort_keys

    def __lt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) < tuple(other_sort_keys)

    def __le__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) <= tuple(other_sort_keys)

    def __gt__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) > tuple(other_sort_keys)

    def __ge__(self, other: Self) -> bool:
        self_sort_keys, other_sort_keys = self._sorting_keys(other)
        return tuple(self_sort_keys) >= tuple(other_sort_keys)

    def duplicate(self) -> Self:
        """Duplicate the current object by doing a deep copy of everything and recreating a new object."""
        return self.model_copy(deep=True)

    @staticmethod
    def is_list_composed_of_hashable_model(items: list[Any]) -> bool:
        return all(isinstance(item, HashableModel) for item in items)

    @staticmethod
    def _organize_sub_items(items: list[HashableModel], shared_ids: set[str]) -> dict[tuple[Any], HashableModel]:
        """Convert a list of HashableModel into a dict with the sorting_id is the key, or the id if it was provided as part of the shared_ids"""
        sub_items = {}
        for item in items:
            if item.id and item.id in shared_ids:
                sub_items[item.id,] = item
                continue
            sub_items[item._sorting_id] = item

        return sub_items

    @staticmethod
    def update_list_hashable_model(
        field_name: str, attr_local: list[HashableModel], attr_other: list[HashableModel]
    ) -> list[Any]:
        """
        Merging the list is not easy,
        we need to create a unique id based on the sorting keys
        and if we have 2 sub items with the same key we can merge them recursively with update()
        """

        # Identify all nodes that are sharing a real IDs
        local_sub_real_ids = {item.id for item in attr_local if item.id}
        other_sub_real_ids = {item.id for item in attr_other if item.id}
        shared_real_ids = local_sub_real_ids & other_sub_real_ids

        local_sub_items = HashableModel._organize_sub_items(items=attr_local, shared_ids=shared_real_ids)
        other_sub_items = HashableModel._organize_sub_items(items=attr_other, shared_ids=shared_real_ids)

        new_list = []

        if len(local_sub_items) != len(attr_local) or len(other_sub_items) != len(attr_other):
            raise ValueError(f"Unable to merge the list for {field_name}, not all items are supporting _sorting_id")

        if duplicates(list(local_sub_items.keys())) or duplicates(list(other_sub_items.keys())):
            raise ValueError(f"Unable to merge the list for {field_name}, some items have the same _sorting_id")

        shared_ids = intersection(list(local_sub_items.keys()), list(other_sub_items.keys()))
        local_only_ids = set(local_sub_items.keys()) - set(shared_ids)
        other_only_ids = set(other_sub_items.keys()) - set(shared_ids)

        new_list = [value for key, value in local_sub_items.items() if key in local_only_ids]
        new_list.extend(
            [
                value
                for key, value in other_sub_items.items()
                if key in other_only_ids and value.state != HashableModelState.ABSENT
            ]
        )

        for item_id in shared_ids:
            other_item = other_sub_items[item_id]
            local_item = local_sub_items[item_id]
            if other_item.state == HashableModelState.ABSENT:
                continue
            new_list.append(local_item.update(other_item))

        return new_list

    def update(self, other: HashableModel) -> Self:
        """Update the current object with the new value from the new one if they are defined.

        Currently this method works for the following type of fields
            int, str, bool, float: If present the value from Other is overwriting the local value
            list[BaseSchemaModel]: The list will be merge if all elements in the list have a _sorting_id and if it's unique.
            HashableModel: the value will be merged using update()

        TODO Implement other fields type like dict
        """

        for field_name in other.model_fields.keys():
            if not hasattr(self, field_name):
                setattr(self, field_name, getattr(other, field_name))
                continue

            attr_other = getattr(other, field_name)
            attr_local = getattr(self, field_name)
            if attr_other is None or attr_local == attr_other:
                continue

            if attr_local is None or isinstance(attr_other, int | str | bool | float):
                setattr(self, field_name, attr_other)
                continue

            if isinstance(attr_local, list) and isinstance(attr_other, list):
                new_attr = self._get_updated_list_value(
                    field_name=field_name, attr_local=attr_local, attr_other=attr_other
                )
                setattr(self, field_name, new_attr)
                continue

            if isinstance(attr_local, HashableModel) and isinstance(attr_other, HashableModel):
                attr_local.update(attr_other)
                continue

        return self

    def _get_updated_list_value(self, field_name: str, attr_local: list[Any], attr_other: list[Any]) -> list[Any]:
        if self.is_list_composed_of_hashable_model(attr_local) and self.is_list_composed_of_hashable_model(attr_other):
            return self.update_list_hashable_model(field_name=field_name, attr_local=attr_local, attr_other=attr_other)

        return attr_other

    def _get_field_names_for_diff(self) -> list[str]:
        return list(self.model_fields.keys())

    def diff(self, other: Self) -> HashableModelDiff:
        in_both, local_only, other_only = compare_lists(
            list1=self._get_field_names_for_diff(), list2=other._get_field_names_for_diff()
        )
        diff_result = HashableModelDiff(added=dict.fromkeys(local_only), removed=dict.fromkeys(other_only))

        for field_name in in_both:
            if field_name.startswith("_") or field_name in self._exclude_from_hash:
                continue

            local_value = getattr(self, field_name)
            other_value = getattr(other, field_name)
            local_signatures = self._get_signature_field(local_value)
            other_signatures = other._get_signature_field(other_value)

            if local_signatures != other_signatures:
                if isinstance(local_value, HashableModel) and isinstance(other_value, HashableModel):
                    diff_result.changed[field_name] = local_value.diff(other=other_value)
                else:
                    diff_result.changed[field_name] = None

        return diff_result
