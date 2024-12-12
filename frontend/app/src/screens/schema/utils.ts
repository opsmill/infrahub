import {
  IModelSchema,
  IProfileSchema,
  iGenericSchema,
  iNodeSchema,
} from "@/state/atoms/schema.atom";

export const isOfKind = (kind: string, schema: IModelSchema) => {
  if (schema.kind === kind) return true;
  if (!isGenericSchema(schema) && schema.inherit_from?.includes(kind)) return true;
  return false;
};

export const isGenericSchema = (schema: IModelSchema): schema is iGenericSchema => {
  return "used_by" in schema;
};

export const isNodeSchema = (schema: IModelSchema): schema is iNodeSchema => {
  return "inherit_from" in schema;
};

export const isProfileSchema = (schema: IModelSchema): schema is IProfileSchema => {
  return schema.namespace === "Profile";
};
