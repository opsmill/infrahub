import type { ModelSchema, ProfileSchema } from "@/entities/schema/domain/model/types";

export const isProfileSchema = (schema: ModelSchema): schema is ProfileSchema => {
  return schema.namespace === "Profile";
};
