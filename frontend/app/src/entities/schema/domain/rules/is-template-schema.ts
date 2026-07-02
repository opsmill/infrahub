import type { ModelSchema, TemplateSchema } from "@/entities/schema/domain/model/schema";

export const isTemplateSchema = (schema: ModelSchema): schema is TemplateSchema => {
  return schema.namespace === "Template";
};
