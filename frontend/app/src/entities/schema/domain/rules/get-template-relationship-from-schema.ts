import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export function getTemplateRelationshipFromSchema(
  schema: ModelSchema
): RelationshipSchema | undefined {
  return schema.relationships?.find(
    (relationship) => relationship.kind === "Template" && relationship.name === "object_template"
  );
}
