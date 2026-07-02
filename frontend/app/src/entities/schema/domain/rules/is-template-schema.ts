import type { ModelSchema, TemplateSchema } from "@/entities/schema/domain/model/types";

export const isTemplateSchema = (schema: ModelSchema): schema is TemplateSchema => {
  return schema.namespace === "Template";
};
