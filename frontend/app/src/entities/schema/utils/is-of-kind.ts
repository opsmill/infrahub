import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export const isOfKind = (kind: string, schema: ModelSchema) => {
  if (schema.kind === kind) return true;
  if (!isGenericSchema(schema) && schema.inherit_from?.includes(kind)) return true;
  return false;
};
