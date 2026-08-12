import type { components } from "@/shared/api/rest/types.generated";

import type { ATTRIBUTE_KIND } from "@/entities/schema/domain/model/attribute-kind";

export type NodeSchema = components["schemas"]["NodeSchemaRead"];
export type GenericSchema = components["schemas"]["GenericSchemaRead"];
export type ProfileSchema = components["schemas"]["ProfileSchemaRead"];
export type TemplateSchema = components["schemas"]["TemplateSchemaRead"];

export type ModelSchema = GenericSchema | NodeSchema | ProfileSchema | TemplateSchema;

export type RelationshipSchema = components["schemas"]["RelationshipSchemaRead"];

export type AttributeSchema =
  | components["schemas"]["TextAttributeRead"]
  | components["schemas"]["NumberAttributeRead"]
  | components["schemas"]["ListAttributeRead"]
  | components["schemas"]["NumberPoolAttributeRead"]
  | components["schemas"]["GenericAttributeRead"];

/**
 * Minimal field descriptor consumed by the filter UI. It is satisfied both by a real read
 * `AttributeSchema`/`RelationshipSchema` and by the lightweight synthetic descriptors the global
 * event filters build (e.g. `{ kind: "Dropdown", choices }` or `{ peer: "CoreAccount" }`). A truthy
 * `peer` marks a relationship field; otherwise `kind` selects the attribute input.
 */
export type FilterFieldSchema = {
  kind?: string;
  peer?: string;
  enum?: unknown[] | null;
  choices?: components["schemas"]["DropdownChoiceRead"][] | null;
};

export type ComputedAttribute =
  | components["schemas"]["ComputedAttributeJinja2Read"]
  | components["schemas"]["ComputedAttributeTransformPythonRead"]
  | components["schemas"]["ComputedAttributeUserRead"];

export type AttributeKind = (typeof ATTRIBUTE_KIND)[keyof typeof ATTRIBUTE_KIND];

export type TextAttributeParameters = components["schemas"]["TextAttributeParametersRead"];
export type NumberAttributeParameters = components["schemas"]["NumberAttributeParametersRead"];

export type Namespace = {
  name: string;
  user_editable: boolean;
};
