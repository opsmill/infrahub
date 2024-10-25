import { IModelSchema } from "@/state/atoms/schema.atom";
import { isGeneric } from "@/utils/common";

export const isOfKind = (kind: string, schema: IModelSchema) => {
  if (schema.kind === kind) return true;
  if (!isGeneric(schema) && schema.inherit_from?.includes(kind)) return true;
  return false;
};
