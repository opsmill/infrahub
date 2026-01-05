import { store } from "@/shared/stores";

import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { GenericSchema, ModelSchema, NodeSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import { isNodeSchema } from "@/entities/schema/utils/is-node-schema";

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
