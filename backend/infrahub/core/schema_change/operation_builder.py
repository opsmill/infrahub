from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from pydantic_core import to_jsonable_python

from infrahub.core.constants import HashableModelState
from infrahub.core.models import HashableModel, HashableModelDiff
from infrahub.core.schema import GenericSchema
from infrahub.core.schema_change.constants import (
    SCHEMA_ELEMENT_NAME_PROPERTY,
    SCHEMA_KIND_NAME_PROPERTIES,
    SCHEMA_PROPERTY_PATH_SEPARATOR,
    SchemaOperationNodeType,
    SchemaOperationSection,
    SchemaOperationType,
)
from infrahub.core.schema_change.operations import (
    INSTANCE_ID_KEY,
    NUMBER_POOL_ID_KEY,
    PARAMETERS_KEY,
    SchemaOperation,
)
from infrahub.core.schema_change.schema_elements import (
    find_element,
    find_element_by_id,
    read_property,
    split_property_path,
)
from infrahub.exceptions import SchemaNotFoundError

if TYPE_CHECKING:
    from pydantic import JsonValue

    from infrahub.core.models import SchemaDiff
    from infrahub.core.schema import (
        AttributeSchema,
        MainSchemaTypes,
        NodeExtensionSchema,
        NodeSchema,
        RelationshipSchema,
        SchemaRoot,
    )
    from infrahub.core.schema.schema_branch import SchemaBranch

ORDER_WEIGHT_KEY = "order_weight"
STATE_PROPERTY = "state"
SECTION_ORDER = (SchemaOperationSection.ATTRIBUTES, SchemaOperationSection.RELATIONSHIPS)
SECTION_NAMES = frozenset(section.value for section in SECTION_ORDER)


@dataclass(frozen=True)
class SchemaOperationBuildResult:
    operations: list[SchemaOperation]
    direct_load_schema: SchemaBranch
    """The schema file laid over a copy of the branch schema, then processed, as a direct load builds it."""

    diff: SchemaDiff
    """The diff from the branch schema to `direct_load_schema`."""


@dataclass
class _ChangedKindOperations:
    """The operations of one changed kind, collected by group so that they come in a fixed order."""

    kind_before: str
    element_removals: list[SchemaOperation] = field(default_factory=list)
    element_additions: list[SchemaOperation] = field(default_factory=list)
    node_properties: list[SchemaOperation] = field(default_factory=list)
    element_properties: list[SchemaOperation] = field(default_factory=list)
    element_renames: list[SchemaOperation] = field(default_factory=list)
    kind_renames: list[SchemaOperation] = field(default_factory=list)

    def ordered(self) -> list[SchemaOperation]:
        return [
            *self.element_removals,
            *self.element_additions,
            *self.node_properties,
            *self.element_properties,
            *self.element_renames,
            *self.kind_renames,
        ]


@dataclass(frozen=True)
class _StatedKind:
    """What a schema file states about one kind, under the kind it has after the load."""

    definitions: list[NodeSchema | GenericSchema]
    extensions: list[NodeExtensionSchema]

    def find_elements(self, section: SchemaOperationSection, name: str) -> list[AttributeSchema | RelationshipSchema]:
        return [
            element
            for holder in [*self.definitions, *self.extensions]
            if (element := find_element(node=holder, section=section, name=name)) is not None
        ]


class SchemaOperationBuilder:
    """Builds the operations of a schema load: the paths of the processed diff that the schema file states."""

    def build(
        self, *, branch_schema: SchemaBranch, schema_root: SchemaRoot, default_branch_schema: SchemaBranch
    ) -> SchemaOperationBuildResult:
        """Lay the schema file over a copy of the branch schema and return the operations it makes.

        Raises the errors that laying a schema file over a schema and processing it raise, and never
        changes `branch_schema`.
        """
        direct_load_schema = branch_schema.duplicate()
        direct_load_schema.load_schema(schema=schema_root)
        stated_kinds = self._stated_kinds(schema_root=schema_root)
        unprocessed = {
            kind: direct_load_schema.get(name=kind) for kind in stated_kinds if direct_load_schema.has(name=kind)
        }
        direct_load_schema.process(default_branch_schema=default_branch_schema)
        diff = branch_schema.diff(other=direct_load_schema)

        operations = [
            operation
            for kind in sorted(diff.removed)
            if kind in unprocessed and stated_kinds[kind].definitions
            for operation in self._removed_kind_operations(
                branch_schema=branch_schema,
                kind=kind,
                unprocessed_node=unprocessed[kind],
                processed_node=direct_load_schema.get(name=kind, duplicate=False),
                stated_kind=stated_kinds[kind],
            )
        ]
        added_kinds = [kind for kind in diff.added if kind in unprocessed and stated_kinds[kind].definitions]
        operations.extend(
            self._node_add(kind=kind, node=unprocessed[kind])
            for kind in sorted(added_kinds, key=lambda kind: (not isinstance(unprocessed[kind], GenericSchema), kind))
        )

        changed_kinds = [
            self._changed_kind_operations(
                branch_schema=branch_schema,
                kind=kind,
                kind_diff=kind_diff,
                unprocessed_node=unprocessed[kind],
                processed_node=direct_load_schema.get(name=kind, duplicate=False),
                stated_kind=stated_kinds[kind],
            )
            for kind, kind_diff in diff.changed.items()
            if kind in unprocessed
        ]
        for kind_operations in sorted(changed_kinds, key=lambda item: item.kind_before):
            operations.extend(kind_operations.ordered())

        return SchemaOperationBuildResult(operations=operations, direct_load_schema=direct_load_schema, diff=diff)

    def _stated_kinds(self, schema_root: SchemaRoot) -> dict[str, _StatedKind]:
        stated_kinds: dict[str, _StatedKind] = {}
        definitions: list[NodeSchema | GenericSchema] = [*schema_root.generics, *schema_root.nodes]
        for item in definitions:
            stated_kinds.setdefault(item.kind, _StatedKind(definitions=[], extensions=[])).definitions.append(item)
        for extension in schema_root.extensions.nodes:
            stated_kinds.setdefault(extension.kind, _StatedKind(definitions=[], extensions=[])).extensions.append(
                extension
            )
        return stated_kinds

    def _kind_before(self, branch_schema: SchemaBranch, kind: str, node: MainSchemaTypes) -> str:
        if node.id is None:
            return kind
        try:
            return branch_schema.get_by_id(id=node.id, duplicate=False).kind
        except SchemaNotFoundError:
            return kind

    def _node_add(self, kind: str, node: MainSchemaTypes) -> SchemaOperation:
        definition = self._definition(model=node)
        for section in SECTION_ORDER:
            elements = definition.get(section.value)
            if not isinstance(elements, list):
                continue
            for element in elements:
                if isinstance(element, dict):
                    self._drop_instance_values(definition=element)
        return SchemaOperation(
            operation_type=SchemaOperationType.NODE_ADD,
            kind=kind,
            node_type=SchemaOperationNodeType.GENERIC
            if isinstance(node, GenericSchema)
            else SchemaOperationNodeType.NODE,
            value=definition,
        )

    def _definition(self, model: HashableModel) -> dict[str, JsonValue]:
        definition: dict[str, JsonValue] = model.model_dump(mode="json", exclude_unset=True, serialize_as_any=True)
        self._drop_instance_values(definition=definition)
        return definition

    def _added_element_definition(
        self,
        element: AttributeSchema | RelationshipSchema,
        processed_element: AttributeSchema | RelationshipSchema | None,
    ) -> dict[str, JsonValue]:
        """Return the definition of an added element, with the order weight that processing gave it when the file has none.

        Processing numbers an element without a weight by its place in the merged list of the kind, which an operation
        does not carry.
        """
        definition = self._definition(model=element)
        if ORDER_WEIGHT_KEY not in definition and processed_element is not None:
            definition[ORDER_WEIGHT_KEY] = processed_element.order_weight
        return definition

    def _drop_instance_values(self, definition: dict[str, JsonValue]) -> None:
        definition.pop(INSTANCE_ID_KEY, None)
        parameters = definition.get(PARAMETERS_KEY)
        if isinstance(parameters, dict):
            parameters.pop(NUMBER_POOL_ID_KEY, None)

    def _removed_kind_operations(
        self,
        branch_schema: SchemaBranch,
        kind: str,
        unprocessed_node: MainSchemaTypes,
        processed_node: MainSchemaTypes,
        stated_kind: _StatedKind,
    ) -> list[SchemaOperation]:
        """Return the operations of a kind that the file marks absent, ending with its removal.

        A load keeps the removed kind in the schema with the other changes that the file states for it merged in, such
        as the attributes and relationships that the file also marks absent, so the operations make those changes
        first.
        """
        kind_before = self._kind_before(branch_schema=branch_schema, kind=kind, node=unprocessed_node)
        branch_node = branch_schema.get(name=kind_before, duplicate=False)
        changes = self._changed_kind_operations(
            branch_schema=branch_schema,
            kind=kind,
            kind_diff=processed_node.diff(other=branch_node),
            unprocessed_node=unprocessed_node,
            processed_node=processed_node,
            stated_kind=stated_kind,
        )
        return [
            *changes.element_removals,
            *changes.element_additions,
            *(operation for operation in changes.node_properties if operation.property_name != STATE_PROPERTY),
            *changes.element_properties,
            *changes.element_renames,
            SchemaOperation(operation_type=SchemaOperationType.NODE_REMOVE, kind=kind_before),
        ]

    def _changed_kind_operations(
        self,
        branch_schema: SchemaBranch,
        kind: str,
        kind_diff: HashableModelDiff,
        unprocessed_node: MainSchemaTypes,
        processed_node: MainSchemaTypes,
        stated_kind: _StatedKind,
    ) -> _ChangedKindOperations:
        kind_before = self._kind_before(branch_schema=branch_schema, kind=kind, node=unprocessed_node)
        branch_node = branch_schema.get(name=kind_before, duplicate=False)
        result = _ChangedKindOperations(kind_before=kind_before)

        for property_name, property_diff in sorted(kind_diff.changed.items()):
            if property_name in SECTION_NAMES or property_name in SCHEMA_KIND_NAME_PROPERTIES:
                continue
            for path in self._property_paths(property_name=property_name, property_diff=property_diff):
                if not any(self._states_property(holder=item, path=path) for item in stated_kind.definitions):
                    continue
                changed_values = self._changed_values(
                    path=path, new_holder=unprocessed_node, previous_holder=branch_node
                )
                if changed_values is None:
                    continue
                value, previous_value = changed_values
                result.node_properties.append(
                    SchemaOperation(
                        operation_type=SchemaOperationType.NODE_PROPERTY,
                        kind=kind_before,
                        property_name=path,
                        value=value,
                        previous_value=previous_value,
                    )
                )

        if stated_kind.definitions:
            result.kind_renames.extend(self._kind_renames(branch_node=branch_node, unprocessed_node=unprocessed_node))

        for section in SECTION_ORDER:
            section_diff = kind_diff.changed.get(section.value)
            if isinstance(section_diff, HashableModelDiff):
                self._collect_element_operations(
                    result=result,
                    section=section,
                    section_diff=section_diff,
                    branch_node=branch_node,
                    unprocessed_node=unprocessed_node,
                    processed_node=processed_node,
                    stated_kind=stated_kind,
                )
        result.element_properties.sort(key=self._element_sort_key)
        result.element_renames.sort(key=self._element_sort_key)
        return result

    def _element_sort_key(self, operation: SchemaOperation) -> tuple[int, str, str]:
        section_position = SECTION_ORDER.index(operation.section) if operation.section is not None else -1
        return section_position, operation.element_name or "", operation.property_name or ""

    def _kind_renames(self, branch_node: MainSchemaTypes, unprocessed_node: MainSchemaTypes) -> list[SchemaOperation]:
        renames: list[SchemaOperation] = []
        renamed_node = branch_node
        for name_property in SCHEMA_KIND_NAME_PROPERTIES:
            value = getattr(unprocessed_node, name_property)
            previous_value = getattr(renamed_node, name_property)
            if value == previous_value:
                continue
            renames.append(
                SchemaOperation(
                    operation_type=SchemaOperationType.NODE_PROPERTY,
                    kind=renamed_node.kind,
                    property_name=name_property,
                    value=value,
                    previous_value=previous_value,
                )
            )
            renamed_node = renamed_node.model_copy(update={name_property: value})
        return renames

    def _collect_element_operations(
        self,
        result: _ChangedKindOperations,
        section: SchemaOperationSection,
        section_diff: HashableModelDiff,
        branch_node: MainSchemaTypes,
        unprocessed_node: MainSchemaTypes,
        processed_node: MainSchemaTypes,
        stated_kind: _StatedKind,
    ) -> None:
        # Processing inherits a removed override again from its generic, so the diff reports that element as changed.
        removed_overrides = {
            element_name
            for element_name in section_diff.changed
            if any(
                item.state == HashableModelState.ABSENT
                for item in stated_kind.find_elements(section=section, name=element_name)
            )
        }
        for element_name in sorted(section_diff.removed.keys() | removed_overrides):
            if stated_kind.find_elements(section=section, name=element_name):
                result.element_removals.append(
                    SchemaOperation(
                        operation_type=SchemaOperationType.ELEMENT_REMOVE,
                        kind=result.kind_before,
                        section=section,
                        element_name=element_name,
                    )
                )

        for element_name in sorted(section_diff.added):
            added = find_element(node=unprocessed_node, section=section, name=element_name)
            if added is None or not stated_kind.find_elements(section=section, name=element_name):
                continue
            result.element_additions.append(
                SchemaOperation(
                    operation_type=SchemaOperationType.ELEMENT_ADD,
                    kind=result.kind_before,
                    section=section,
                    element_name=element_name,
                    value=self._added_element_definition(
                        element=added,
                        processed_element=find_element(node=processed_node, section=section, name=element_name),
                    ),
                )
            )

        for element_name, element_diff in section_diff.changed.items():
            element = find_element(node=unprocessed_node, section=section, name=element_name)
            file_elements = stated_kind.find_elements(section=section, name=element_name)
            if (
                element is None
                or element_name in removed_overrides
                or not file_elements
                or not isinstance(element_diff, HashableModelDiff)
            ):
                continue
            element_before = None
            if element.id is not None:
                element_before = find_element_by_id(node=branch_node, section=section, element_id=element.id)
            if element_before is None:
                element_before = find_element(node=branch_node, section=section, name=element_name)
            if element_before is None:
                continue

            for property_name, property_diff in sorted(element_diff.changed.items()):
                for path in self._property_paths(property_name=property_name, property_diff=property_diff):
                    if not any(self._states_property(holder=item, path=path) for item in file_elements):
                        continue
                    changed_values = self._changed_values(path=path, new_holder=element, previous_holder=element_before)
                    if changed_values is None:
                        continue
                    value, previous_value = changed_values
                    operation = SchemaOperation(
                        operation_type=SchemaOperationType.ELEMENT_PROPERTY,
                        kind=result.kind_before,
                        section=section,
                        element_name=element_before.name,
                        property_name=path,
                        value=value,
                        previous_value=previous_value,
                    )
                    if path == SCHEMA_ELEMENT_NAME_PROPERTY:
                        result.element_renames.append(operation)
                    else:
                        result.element_properties.append(operation)

    def _property_paths(self, property_name: str, property_diff: HashableModelDiff | None) -> list[str]:
        """Return the dotted path of each changed leaf property, keeping a nested model whole when its fields differ."""
        if property_diff is None or property_diff.added or property_diff.removed or not property_diff.changed:
            return [property_name]
        return [
            path
            for sub_name, sub_diff in sorted(property_diff.changed.items())
            for path in self._property_paths(
                property_name=f"{property_name}{SCHEMA_PROPERTY_PATH_SEPARATOR}{sub_name}", property_diff=sub_diff
            )
        ]

    def _states_property(self, holder: object, path: str) -> bool:
        """Return whether the file states a property, or another field of the nested model that holds it.

        A nested model can replace its other fields when the file sets one of them, as the number pool parameters do
        when the file declares the range by its bounds or by a list of ranges.
        """
        if read_property(holder=holder, property_name=path) is not None:
            return True
        *parents, _ = split_property_path(path)
        if not parents:
            return False
        parent = read_property(holder=holder, property_name=SCHEMA_PROPERTY_PATH_SEPARATOR.join(parents))
        if not isinstance(parent, HashableModel):
            return False
        declared_fields = type(parent).model_fields.keys() - HashableModel.model_fields.keys()
        return any(getattr(parent, field_name) is not None for field_name in declared_fields)

    def _changed_values(
        self, path: str, new_holder: object, previous_holder: object
    ) -> tuple[JsonValue, JsonValue] | None:
        """Return the new and the previous value of a property as JSON values, or `None` when they are equal."""
        value: JsonValue = to_jsonable_python(
            read_property(holder=new_holder, property_name=path), serialize_as_any=True
        )
        previous_value: JsonValue = to_jsonable_python(
            read_property(holder=previous_holder, property_name=path), serialize_as_any=True
        )
        if value == previous_value:
            return None
        return value, previous_value
