import type { components } from "@/shared/api/rest/types.generated";

import type { ATTRIBUTE_KIND } from "@/entities/schema/constants";

export type NodeSchema = components["schemas"]["APINodeSchema"];
export type GenericSchema = components["schemas"]["APIGenericSchema"];
export type ProfileSchema = components["schemas"]["APIProfileSchema"];
export type TemplateSchema = components["schemas"]["APITemplateSchema"];

export type ModelSchema = GenericSchema | NodeSchema | ProfileSchema | TemplateSchema;

export type RelationshipSchema = components["schemas"]["RelationshipSchema"];

export type AttributeSchema = components["schemas"]["AttributeSchema-Output"];

export type AttributeKind = (typeof ATTRIBUTE_KIND)[keyof typeof ATTRIBUTE_KIND];

export type TextAttributeParameters = components["schemas"]["TextAttributeParameters"];
export type NumberAttributeParameters = components["schemas"]["NumberAttributeParameters"];

export type Namespace = {
  name: string;
  user_editable: boolean;
};
