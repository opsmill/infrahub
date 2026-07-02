import type { AttributeSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";

export const canDisplayResetActions = (
  fieldSchema: AttributeSchema | RelationshipSchema | undefined,
  isBulkUpdate?: boolean
) => {
  return !!isBulkUpdate && !!fieldSchema?.optional;
};
