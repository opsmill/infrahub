import type { ModelSchema, NodeSchema } from "@/entities/schema/domain/model/schema";

export const isNodeSchema = (schema: ModelSchema): schema is NodeSchema => {
  return "inherit_from" in schema;
};
