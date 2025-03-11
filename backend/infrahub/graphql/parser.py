from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from graphql.language import (
    DirectiveNode,
    FieldNode,
    InlineFragmentNode,
    ListValueNode,
    NameNode,
    SelectionSetNode,
    StringValueNode,
)
from infrahub_sdk.utils import deep_merge_dict

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema


@dataclass
class FieldEnricher:
    key: str
    node: FieldNode
    path: str
    fields: dict = field(default_factory=dict)


async def extract_selection(field_node: FieldNode, schema: NodeSchema) -> dict:
    graphql_extractor = GraphQLExtractor(field_node=field_node, schema=schema)
    return await graphql_extractor.get_fields()


class GraphQLExtractor:
    def __init__(self, field_node: FieldNode, schema: NodeSchema) -> None:
        self.field_node = field_node
        self.schema = schema
        self.typename_paths: dict[str, list[FieldEnricher]] = {}
        self.node_path: dict[str, list[FieldEnricher]] = {}

    def _define_node_path(self, path: str) -> None:
        if path not in self.node_path:
            self.node_path[path] = []

    async def get_fields(self) -> dict:
        return await self.extract_fields(selection_set=self.field_node.selection_set) or {}

    def _process_expand_directive(self, path: str, directive: DirectiveNode) -> None:
        excluded_fields = []
        for argument in directive.arguments:
            if argument.name.value == "exclude":
                if isinstance(argument.value, ListValueNode):
                    excluded_fields.extend(
                        [value.value for value in argument.value.values if isinstance(value, StringValueNode)]
                    )

        if path not in self.typename_paths:
            self.typename_paths[path] = []
        self.typename_paths[path].append(
            FieldEnricher(
                key="__typename",
                node=FieldNode(
                    kind="field",
                    name=NameNode(kind="name", value="__typename"),
                    directives=[],
                    arguments=[],
                ),
                path=f"{path}/__typename/",
            )
        )
        if path == "/edges/node/":
            self._define_node_path(path=path)

            self.node_path[path].append(
                FieldEnricher(
                    key="id",
                    node=FieldNode(
                        kind="field",
                        name=NameNode(kind="name", value="id"),
                        directives=[],
                        arguments=[],
                    ),
                    path=f"{path}id/",
                    fields={"id": None},
                )
            )
            attribute_enrichers = []
            attributes = [attribute for attribute in self.schema.attributes if attribute.name not in excluded_fields]
            for attribute in attributes:
                attribute_path = f"{path}{attribute.name}/"
                self._define_node_path(path=attribute_path)
                field_attributes = {"value": None, "is_default": None, "is_from_profile": None}

                enrichers = [
                    FieldEnricher(
                        key=attribute.name,
                        node=FieldNode(
                            kind="field",
                            name=NameNode(
                                kind="name",
                                value=key,
                                directives=[],
                                arguments=[],
                            ),
                        ),
                        path=attribute_path,
                        fields={key: None},
                    )
                    for key in field_attributes
                ]

                self.node_path[attribute_path].extend(enrichers)
                attribute_enrichers.append(
                    FieldNode(
                        kind="field",
                        name=NameNode(kind="name", value=attribute.name),
                        selection_set=SelectionSetNode(selections=tuple(enrichers)),
                    )
                )

            self._define_node_path(path=path)
            self.node_path[path].append(
                FieldEnricher(
                    key="node",
                    path=path,
                    node=FieldNode(
                        kind="field",
                        name=NameNode(kind="name", value="node"),
                        selection_set=SelectionSetNode(selections=tuple(attribute_enrichers)),
                    ),
                    fields={attribute.name: field_attributes for attribute in self.schema.attributes},
                )
            )

    def process_directives(self, node: FieldNode, path: str) -> None:
        for directive in node.directives:
            if directive.name.value == "expand":
                self._process_expand_directive(path=path, directive=directive)

    def apply_directives(self, selection_set: SelectionSetNode, fields: dict, path: str) -> dict:
        if path in self.typename_paths:
            for node in self.typename_paths[path]:
                if "__typename" not in fields:
                    selections = list(selection_set.selections)
                    selections.append(node.node)
                    selection_set.selections = tuple(selections)

        if path in self.node_path:
            for node in self.node_path[path]:
                if node.key not in fields:
                    fields = deep_merge_dict(dicta=fields.copy(), dictb=node.fields)
                    selections = list(selection_set.selections)
                    selections.append(node.node)
                    selection_set.selections = tuple(selections)

            undefined_paths = [key for key in self.node_path if is_child_path(path=path, child=key)]

            for undefined in undefined_paths:
                for sub_node in self.node_path[undefined]:
                    selections = list(selection_set.selections)
                    selections.append(
                        FieldNode(
                            kind="field",
                            name=NameNode(kind="name", value=sub_node.key),
                            selection_set=SelectionSetNode(selections=(sub_node.node,)),
                        )
                    )
                    selection_set.selections = tuple(selections)

            del self.node_path[path]

        return fields

    async def extract_fields(
        self, selection_set: SelectionSetNode | None, path: str = "/"
    ) -> dict[str, dict | None] | None:
        """Extract fields and apply Directives"""
        if not selection_set:
            return None

        fields: dict[str, dict | None] = {}
        for node in selection_set.selections:
            sub_selection_set = getattr(node, "selection_set", None)
            if isinstance(node, FieldNode):
                node_path = f"{path}{node.name.value}/"
                self.process_directives(node=node, path=node_path)

                value = await self.extract_fields(sub_selection_set, path=node_path)
                if node.name.value not in fields:
                    fields[node.name.value] = value
                elif isinstance(fields[node.name.value], dict) and isinstance(value, dict):
                    fields[node.name.value].update(value)  # type: ignore[union-attr]

            elif isinstance(node, InlineFragmentNode):
                for sub_node in node.selection_set.selections:
                    if isinstance(sub_node, FieldNode):
                        sub_node_path = f"{path}{sub_node.name.value}/"
                        sub_sub_selection_set = getattr(sub_node, "selection_set", None)
                        value = await self.extract_fields(sub_sub_selection_set, path=sub_node_path)
                        if sub_node.name.value not in fields:
                            fields[sub_node.name.value] = await self.extract_fields(
                                sub_sub_selection_set, path=sub_node_path
                            )
                        elif isinstance(fields[sub_node.name.value], dict) and isinstance(value, dict):
                            fields[sub_node.name.value].update(value)  # type: ignore[union-attr]

        return self.apply_directives(selection_set=selection_set, fields=fields, path=path)


def is_child_path(path: str, child: str) -> bool:
    if child.startswith(path) and len(child) > len(path):
        return True
    return False
