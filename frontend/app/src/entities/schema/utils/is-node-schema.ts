import type { ModelSchema, NodeSchema } from "@/entities/schema/types";

export const isNodeSchema = (schema: ModelSchema): schema is NodeSchema => {
  return "inherit_from" in schema;
};
