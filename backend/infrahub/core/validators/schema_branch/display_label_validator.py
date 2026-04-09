from __future__ import annotations

from typing import TYPE_CHECKING

from infrahub_sdk.template.exceptions import JinjaTemplateError, JinjaTemplateOperationViolationError
from infrahub_sdk.template.filters import ExecutionContext

from infrahub.computed_attribute.jinja2 import InfrahubJinja2Template
from infrahub.core.constants import SchemaElementPathType
from infrahub.core.schema import MainSchemaTypes, NodeSchema
from infrahub.core.schema.schema_branch_display import DisplayLabels

from .interface import SchemaBranchValidator

if TYPE_CHECKING:
    from infrahub.core.schema.schema_branch import SchemaBranch

from infrahub import config


def _format_display_label_component(component: str) -> str:
    """Return correct format for display_label.

    Previously both the format of 'name' and 'name__value' was
    supported; this function ensures that the proper 'name__value'
    format is used.
    """
    if "__" in component:
        return component
    return f"{component}__value"


class DisplayLabelValidator(SchemaBranchValidator):
    def check(self, schema_branch: SchemaBranch) -> None:
        inherited_from_labels = self.validate_display_labels(schema_branch)
        self.validate_display_label(schema_branch, skip_validation=inherited_from_labels)

    # ------------------------------------------------------------------
    # validate_display_labels (deprecated display_labels field)
    # ------------------------------------------------------------------

    def validate_display_labels(self, schema_branch: SchemaBranch) -> set[str]:
        """Validate and propagate the deprecated display_labels field.

        Returns the names of node schemas that had display_labels set via
        generic inheritance (not defined directly). These nodes should have
        their converted display_label skipped during validation in
        validate_display_label because inherited attributes may not yet be
        visible without process_inheritance.
        """
        inherited_nodes: set[str] = set()
        for name in schema_branch.all_names:
            node_schema = schema_branch.get(name=name, duplicate=False)

            if node_schema.display_labels:
                for path in node_schema.display_labels:
                    schema_branch.validate_schema_path(
                        node_schema=node_schema,
                        path=path,
                        allowed_path_types=SchemaElementPathType.ATTR,
                        element_name="display_labels",
                    )
            elif isinstance(node_schema, NodeSchema):
                generic_display_labels = []
                for generic in node_schema.inherit_from:
                    generic_schema = schema_branch.get(name=generic, duplicate=False)
                    if generic_schema.display_labels:
                        generic_display_labels.append(generic_schema.display_labels)

                if len(generic_display_labels) == 1:
                    # Only assign node display labels if a single generic has them defined
                    node_schema.display_labels = generic_display_labels[0]
                    inherited_nodes.add(name)

        return inherited_nodes

    # ------------------------------------------------------------------
    # validate_display_label (new display_label field)
    # ------------------------------------------------------------------

    def validate_display_label(self, schema_branch: SchemaBranch, skip_validation: set[str] | None = None) -> None:
        """Validate and normalise the display_label field.

        skip_validation: names of node schemas whose display_label was
        derived from an inherited display_labels value. The generic already
        validates the path, so re-validating on the child (which may not
        have gone through process_inheritance yet) is both redundant and
        error-prone.
        """
        schema_branch.display_labels = DisplayLabels()
        nodes_to_skip: set[str] = skip_validation or set()

        # Pass 1: convert legacy display_labels to display_label for all schemas.
        # Must run before inheritance so generics are fully resolved before children read them.
        for name in schema_branch.all_names:
            node_schema = schema_branch.get(name=name, duplicate=False)
            if node_schema.display_label is not None or not node_schema.display_labels:
                continue
            update_candidate = schema_branch.get(name=name, duplicate=True)
            if len(node_schema.display_labels) == 1:
                # Single attribute — convert directly
                update_candidate.display_label = _format_display_label_component(
                    component=node_schema.display_labels[0]
                )
            else:
                # Multiple attributes — build a Jinja2 template
                update_candidate.display_label = " ".join(
                    [
                        f"{{{{ {_format_display_label_component(component=display_label)} }}}}"
                        for display_label in node_schema.display_labels
                    ]
                )
            schema_branch.set(name=name, schema=update_candidate)

        # Pass 2: inherit display_label from a parent generic when the node defines neither field.
        # Validation is skipped for inherited nodes because the generic's display_label
        # is already validated on the generic itself.
        for name in schema_branch.all_names:
            node_schema = schema_branch.get(name=name, duplicate=False)
            if (
                node_schema.display_label is not None
                or node_schema.display_labels
                or not isinstance(node_schema, NodeSchema)
            ):
                continue
            inherited = [
                schema_branch.get(name=generic, duplicate=False).display_label
                for generic in node_schema.inherit_from
                if schema_branch.get(name=generic, duplicate=False).display_label
            ]
            if len(inherited) == 1:
                update_candidate = schema_branch.get(name=name, duplicate=True)
                update_candidate.display_label = inherited[0]
                schema_branch.set(name=name, schema=update_candidate)
                nodes_to_skip.add(name)

        # Pass 3: validate display_label on all schemas that have one set.
        for name in schema_branch.all_names:
            if name in nodes_to_skip:
                continue
            node_schema = schema_branch.get(name=name, duplicate=False)
            if not node_schema.display_label:
                continue
            self._validate_one(schema_branch=schema_branch, node=node_schema)

    def _validate_one(self, schema_branch: SchemaBranch, node: MainSchemaTypes) -> None:
        if not node.display_label:
            return

        if not any(c in node.display_label for c in "{}"):
            schema_path = schema_branch.validate_schema_path(
                node_schema=node,
                path=node.display_label,
                allowed_path_types=SchemaElementPathType.ATTR_WITH_PROP,
                element_name="display_label - non Jinja2",
            )
            if schema_path.attribute_schema and node.is_node_schema and node.namespace not in ["Internal", "Schema"]:
                schema_branch.display_labels.register_attribute_based_display_label(
                    kind=node.kind, attribute_name=schema_path.attribute_schema.name
                )
            return

        jinja_template = InfrahubJinja2Template(template=node.display_label)
        context = ExecutionContext.CORE
        if not config.SETTINGS.security.restrict_untrusted_jinja2_filters:
            context |= ExecutionContext.LOCAL
        try:
            variables = jinja_template.get_variables()
            jinja_template.validate(context=context)
        except (JinjaTemplateOperationViolationError, JinjaTemplateError) as exc:
            raise ValueError(
                f"{node.kind}: display_label is set to a jinja2 template, but has an invalid template: {exc.message}"
            ) from exc

        allowed_path_types = (
            SchemaElementPathType.ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_MANDATORY_ATTR_WITH_PROP
            | SchemaElementPathType.REL_ONE_ATTR_WITH_PROP
        )
        for variable in variables:
            schema_path = schema_branch.validate_schema_path(
                node_schema=node, path=variable, allowed_path_types=allowed_path_types, element_name="display_label"
            )

            if schema_path.is_type_attribute and schema_path.active_attribute_schema.name == "display_label":
                raise ValueError(f"{node.kind}: display_label the '{variable}' variable is a reference to itself")

            if node.is_node_schema and node.namespace not in ["Internal", "Schema"]:
                schema_branch.display_labels.register_template_schema_path(
                    kind=node.kind, schema_path=schema_path, template=node.display_label
                )
