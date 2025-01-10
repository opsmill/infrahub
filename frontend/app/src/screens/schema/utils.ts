import { store } from "@/shared/stores";
import {
  IModelSchema,
  IProfileSchema,
  iGenericSchema,
  iNodeSchema,
  schemaState,
} from "@/screens/schema/schema.atom";

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

export const isHierarchicalSchema = (
  schema: IModelSchema
): schema is IModelSchema & { hierarchy: string } => {
  return "hierarchy" in schema && !!schema.hierarchy;
};

export const getRootSchemaOfHierarchicalSchema = (schema: iNodeSchema): iNodeSchema => {
  const nodes = store.get(schemaState);
  const parentSchema = nodes.find(({ kind }) => kind === schema.parent);

  if (!parentSchema) return schema;
  return getRootSchemaOfHierarchicalSchema(parentSchema);
};
