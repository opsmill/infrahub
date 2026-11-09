import { store } from "@/shared/stores";

import type { GenericSchema, ModelSchema, NodeSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { isNodeSchema } from "@/entities/schema/domain/rules/is-node-schema";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

export const isHierarchicalSchema = (
  schema: ModelSchema
): schema is ModelSchema & { hierarchy: string } => {
  return "hierarchy" in schema && !!schema.hierarchy;
};

export const getGenericSchemaOfHierarchy = (schema: ModelSchema): GenericSchema | null => {
  if (isGenericSchema(schema)) {
    return schema.hierarchical ? schema : null;
  }

  if (isNodeSchema(schema)) {
    const genericSchemas = store.get(genericSchemasAtom);
    return genericSchemas.find(({ kind }) => kind === schema.hierarchy) ?? null;
  }

  return null;
};

export const getRootSchemaOfHierarchicalSchema = (schema: NodeSchema): NodeSchema => {
  const nodes = store.get(nodeSchemasAtom);
  const parentSchema = nodes.find(({ kind }) => kind === schema.parent);

  if (!parentSchema) return schema;
  return getRootSchemaOfHierarchicalSchema(parentSchema);
};
