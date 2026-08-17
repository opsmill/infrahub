import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export const isRelationshipSchema = (
  fieldSchema: AttributeSchema | RelationshipSchema
): fieldSchema is RelationshipSchema => {
  return "peer" in fieldSchema;
};
