import { store } from "@/shared/stores";

import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";
import type { ModelSchema, NodeSchema } from "@/entities/schema/types";

export const isHierarchicalSchema = (
  schema: ModelSchema
): schema is ModelSchema & { hierarchy: string } => {
  return "hierarchy" in schema && !!schema.hierarchy;
};

export const getRootSchemaOfHierarchicalSchema = (schema: NodeSchema): NodeSchema => {
  const nodes = store.get(nodeSchemasAtom);
  const parentSchema = nodes.find(({ kind }) => kind === schema.parent);

  if (!parentSchema) return schema;
  return getRootSchemaOfHierarchicalSchema(parentSchema);
};
