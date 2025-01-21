import { ATTRIBUTE_KIND } from "@/entities/schema/constants";
import { components } from "@/shared/api/rest/types.generated";

export type RelationshipSchema = components["schemas"]["RelationshipSchema"];

export type AttributeSchema = components["schemas"]["AttributeSchema-Output"];

export type AttributeKind = (typeof ATTRIBUTE_KIND)[keyof typeof ATTRIBUTE_KIND];
