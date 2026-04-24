import type { ModelSchema } from "@/entities/schema/types";

export function hasExtraFields(schema: ModelSchema): boolean {
  const attributes = schema.attributes ?? [];
  const relationships = schema.relationships ?? [];

  return [...attributes, ...relationships].some((field) => field.display === "extra");
}
