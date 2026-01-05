import type { ModelSchema, TemplateSchema } from "@/entities/schema/types";

export const isTemplateSchema = (schema: ModelSchema): schema is TemplateSchema => {
  return schema.namespace === "Template";
};
