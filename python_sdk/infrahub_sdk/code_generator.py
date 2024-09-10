from typing import Any, Mapping, Optional

import jinja2

from infrahub_sdk import protocols as sdk_protocols
from infrahub_sdk.ctl.constants import PROTOCOLS_TEMPLATE
from infrahub_sdk.schema import (
    AttributeSchema,
    GenericSchema,
    MainSchemaTypes,
    NodeSchema,
    ProfileSchema,
    RelationshipSchema,
)


class CodeGenerator:
    def __init__(self, schema: dict[str, MainSchemaTypes]):
        self.generics: dict[str, GenericSchema] = {}
        self.nodes: dict[str, NodeSchema] = {}
        self.profiles: dict[str, ProfileSchema] = {}

        for name, schema_type in schema.items():
            if isinstance(schema_type, GenericSchema):
                self.generics[name] = schema_type
            if isinstance(schema_type, NodeSchema):
                self.nodes[name] = schema_type
            if isinstance(schema_type, ProfileSchema):
                self.profiles[name] = schema_type

        self.base_protocols = [
            e
            for e in dir(sdk_protocols)
            if not e.startswith("__")
            and not e.endswith("__")
            and e
            not in ("TYPE_CHECKING", "CoreNode", "Optional", "Protocol", "Union", "annotations", "runtime_checkable")
        ]

        self.sorted_generics = self._sort_and_filter_models(self.generics, filters=["CoreNode"] + self.base_protocols)
        self.sorted_nodes = self._sort_and_filter_models(self.nodes, filters=["CoreNode"] + self.base_protocols)
        self.sorted_profiles = self._sort_and_filter_models(
            self.profiles, filters=["CoreProfile"] + self.base_protocols
        )

    def render(self, sync: bool = True) -> str:
        jinja2_env = jinja2.Environment(loader=jinja2.BaseLoader(), trim_blocks=True, lstrip_blocks=True)
        jinja2_env.filters["inheritance"] = self._jinja2_filter_inheritance
        jinja2_env.filters["render_attribute"] = self._jinja2_filter_render_attribute
        jinja2_env.filters["render_relationship"] = self._jinja2_filter_render_relationship

        template = jinja2_env.from_string(PROTOCOLS_TEMPLATE)
        return template.render(
            generics=self.sorted_generics,
            nodes=self.sorted_nodes,
            profiles=self.sorted_profiles,
            base_protocols=self.base_protocols,
            sync=sync,
        )

    @staticmethod
    def _jinja2_filter_inheritance(value: dict[str, Any]) -> str:
        inherit_from: list[str] = value.get("inherit_from", [])

        if not inherit_from:
            return "CoreNode"
        return ", ".join(inherit_from)

    @staticmethod
    def _jinja2_filter_render_attribute(value: AttributeSchema) -> str:
        attribute_kind_map = {
            "boolean": "Boolean",
            "datetime": "DateTime",
            "dropdown": "Dropdown",
            "hashedpassword": "HashedPassword",
            "iphost": "IPHost",
            "ipnetwork": "IPNetwork",
            "json": "JSONAttribute",
            "list": "ListAttribute",
            "number": "Integer",
            "password": "String",
            "text": "String",
            "textarea": "String",
            "url": "URL",
        }

        name = value.name
        kind = value.kind

        attribute_kind = attribute_kind_map[kind.lower()]
        if value.optional:
            attribute_kind = f"{attribute_kind}Optional"

        return f"{name}: {attribute_kind}"

    @staticmethod
    def _jinja2_filter_render_relationship(value: RelationshipSchema, sync: bool = False) -> str:
        name = value.name
        cardinality = value.cardinality

        type_ = "RelatedNode"
        if cardinality == "many":
            type_ = "RelationshipManager"

        if sync:
            type_ += "Sync"

        return f"{name}: {type_}"

    @staticmethod
    def _sort_and_filter_models(
        models: Mapping[str, MainSchemaTypes], filters: Optional[list[str]] = None
    ) -> list[MainSchemaTypes]:
        if filters is None:
            filters = ["CoreNode"]

        filtered: list[MainSchemaTypes] = []
        for name, model in models.items():
            if name in filters:
                continue
            filtered.append(model)

        return sorted(filtered, key=lambda k: k.name)
