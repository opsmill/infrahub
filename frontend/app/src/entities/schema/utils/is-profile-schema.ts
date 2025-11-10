import type { ModelSchema, ProfileSchema } from "@/entities/schema/types";

export const isProfileSchema = (schema: ModelSchema): schema is ProfileSchema => {
  return schema.namespace === "Profile";
};
