import { AttributeSchema, RelationshipSchema } from "@/entities/schema/types";

export const canRenderReset = (
  fieldSchema: AttributeSchema | RelationshipSchema,
  isBulkUpdate?: boolean
) => {
  return !!isBulkUpdate && !!fieldSchema?.optional;
};
