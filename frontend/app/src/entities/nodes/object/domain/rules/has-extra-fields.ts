import { isRepositoryDeliveryAttribute } from "@/entities/repository/domain/rules/is-repository-delivery-attribute";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export function hasExtraFields(schema: ModelSchema): boolean {
  const attributes = schema.attributes ?? [];
  const relationships = schema.relationships ?? [];

  return [...attributes, ...relationships].some(
    (field) => field.display === "extra" && !isRepositoryDeliveryAttribute(schema, field.name)
  );
}
