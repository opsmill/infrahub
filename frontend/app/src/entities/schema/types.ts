import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { components } from "@/shared/api/rest/types.generated";

export type NodeSchema = components["schemas"]["APINodeSchema"];
export type GenericSchema = components["schemas"]["APIGenericSchema"];
export type ProfileSchema = components["schemas"]["APIProfileSchema"];

export type ModelSchema = GenericSchema | NodeSchema | ProfileSchema;

export type RelationshipSchema = components["schemas"]["RelationshipSchema"];

export type AttributeSchema = components["schemas"]["AttributeSchema-Output"];

export type AttributeKind = (typeof ATTRIBUTE_KIND)[keyof typeof ATTRIBUTE_KIND];

export type Namespace = {
  name: string;
  user_editable: boolean;
};
