import type { ModelSchema } from "@/entities/schema/types";

/**
 * Determines if form submission should be allowed even when the form data is empty.
 * This is true when all attributes in the schema are read-only (e.g., NumberPool fields,
 * computed attributes), as the server will populate these values.
 */
export const shouldAllowEmptySubmission = (schema: ModelSchema): boolean => {
  const attributes = schema.attributes ?? [];
  const relationships = schema.relationships ?? [];

  // Allow submission if all attributes and relationships are read-only
  // (empty arrays return true for .every(), handling the no-fields case)
  return attributes.every((attr) => attr.read_only) && relationships.every((rel) => rel.read_only);
};
