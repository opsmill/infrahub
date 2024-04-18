from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from graphql.language import FieldNode, InlineFragmentNode, NameNode, SelectionSetNode

if TYPE_CHECKING:
    from infrahub.core.schema import NodeSchema


@dataclass
class FieldEnricher:
    key: str
    node: FieldNode
    path: str
    fields: dict = field(default_factory=dict)


async def extract_selection(field_node: FieldNode, schema: NodeSchema) -> dict:
    graqphql_extractor = GraphQLExtracter(field_node=field_node, schema=schema)
    return await graqphql_extractor.get_fields()


class GraphQLExtracter:
    def __init__(self, field_node: FieldNode, schema: NodeSchema) -> None:
        self.field_node = field_node
        self.schema = schema
        self.typename_paths: dict[str, list[FieldEnricher]] = {}
        self.node_path: dict[str, list[FieldEnricher]] = {}

    async def get_fields(self) -> dict:
        return await self.extract_fields(selection_set=self.field_node.selection_set) or {}

    def process_directives(self, node: FieldNode, path: str) -> None:
        for directive in node.directives:
            if directive.name.value == "expand":
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
                    if path not in self.node_path:
                        self.node_path[path] = []

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
                    for attribute in self.schema.attributes:
                        attribute_path = f"{path}{attribute.name}/"
                        if attribute_path not in self.node_path:
                            self.node_path[attribute_path] = []

                        attribute_enricher_node = FieldNode(
                            kind="field",
                            name=NameNode(
                                kind="name",
                                value="value",
                                directives=[],
                                arguments=[],
                            ),
                        )

                        attribute_enricher = FieldEnricher(
                            key=attribute.name,
                            node=attribute_enricher_node,
                            path=attribute_path,
                            fields={"value": None},
                        )
                        self.node_path[attribute_path].append(attribute_enricher)
                        attribute_enrichers.append(
                            FieldNode(
                                kind="field",
                                name=NameNode(kind="name", value=attribute.name),
                                selection_set=SelectionSetNode(selections=tuple([attribute_enricher])),
                            )
                        )

                    if path not in self.node_path:
                        self.node_path[path] = []
                    self.node_path[path].append(
                        FieldEnricher(
                            key="node",
                            path=path,
                            node=FieldNode(
                                kind="field",
                                name=NameNode(kind="name", value="node"),
                                selection_set=SelectionSetNode(selections=tuple(attribute_enrichers)),
                            ),
                            fields={attribute.name: {"value": None} for attribute in self.schema.attributes},
                        )
                    )

    def apply_directives(self, selection_set: SelectionSetNode, fields: dict, path: str) -> None:
        if path in self.typename_paths:
            for node in self.typename_paths[path]:
                if "__typename" not in fields:
                    selections = list(selection_set.selections)
                    selections.append(node.node)
                    selection_set.selections = tuple(selections)

        if path in self.node_path:
            for node in self.node_path[path]:
                if node.key not in fields:
                    fields.update(node.fields)
                    selections = list(selection_set.selections)
                    selections.append(node.node)
                    selection_set.selections = tuple(selections)

            undefined_paths = [key for key in self.node_path if key.startswith(path) and len(key) > len(path)]
            for undefined in undefined_paths:
                for sub_node in self.node_path[undefined]:
                    selections = list(selection_set.selections)
                    selections.append(
                        FieldNode(
                            kind="field",
                            name=NameNode(kind="name", value=sub_node.key),
                            selection_set=SelectionSetNode(selections=tuple([sub_node.node])),
                        )
                    )
                    selection_set.selections = tuple(selections)

            del self.node_path[path]

    async def extract_fields(
        self, selection_set: Optional[SelectionSetNode], path: str = "/"
    ) -> Optional[dict[str, Optional[dict]]]:
        """Exctract fields and apply Directives"""

        if not selection_set:
            return None

        fields: dict[str, Optional[dict]] = {}
        for node in selection_set.selections:
            sub_selection_set = getattr(node, "selection_set", None)
            if isinstance(node, FieldNode):
                node_path = f"{path}{node.name.value}/"
                self.process_directives(node=node, path=node_path)

                value = await self.extract_fields(sub_selection_set, path=f"{path}{node.name.value}/")
                if node.name.value not in fields:
                    fields[node.name.value] = value
                elif isinstance(fields[node.name.value], dict) and isinstance(value, dict):
                    fields[node.name.value].update(value)  # type: ignore[union-attr]

            elif isinstance(node, InlineFragmentNode):
                for sub_node in node.selection_set.selections:
                    if isinstance(sub_node, FieldNode):
                        sub_sub_selection_set = getattr(sub_node, "selection_set", None)
                        value = await self.extract_fields(sub_sub_selection_set, path=f"{path}{sub_node.name.value}/")
                        if sub_node.name.value not in fields:
                            fields[sub_node.name.value] = await self.extract_fields(
                                sub_sub_selection_set, path=f"{path}{sub_node.name.value}/"
                            )
                        elif isinstance(fields[sub_node.name.value], dict) and isinstance(value, dict):
                            fields[sub_node.name.value].update(value)  # type: ignore[union-attr]

        self.apply_directives(selection_set=selection_set, fields=fields, path=path)

        return fields
