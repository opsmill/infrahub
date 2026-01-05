import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export const canDisplayResetActions = (
  fieldSchema: AttributeSchema | RelationshipSchema,
  isBulkUpdate?: boolean
) => {
  return !!isBulkUpdate && !!fieldSchema?.optional;
};
