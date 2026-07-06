import type { GenericSchema, ModelSchema } from "@/entities/schema/domain/model/schema";

export const isGenericSchema = (schema: ModelSchema): schema is GenericSchema => {
  return "used_by" in schema;
};
