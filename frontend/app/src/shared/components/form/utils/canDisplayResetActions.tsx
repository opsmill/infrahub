import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export const canDisplayResetActions = (
  fieldSchema: AttributeSchema | RelationshipSchema | undefined,
  isBulkUpdate?: boolean
) => {
  return !!isBulkUpdate && !!fieldSchema?.optional;
};
