import type { ModelSchema } from "@/entities/schema/types";

/**
 * Determines if form submission should be allowed even when the form data is empty.
 * This is true when all attributes in the schema are read-only (e.g., NumberPool fields,
 * computed attributes), as the server will populate these values.
 */
export const shouldAllowEmptySubmission = (schema: ModelSchema): boolean => {
  const attributes = schema.attributes ?? [];

  // If there are no attributes, allow submission
  if (attributes.length === 0) {
    return true;
  }

  // Allow submission if all attributes are read-only
  return attributes.every((attr) => attr.read_only);
};
