import { READONLY_REPOSITORY_KIND } from "@/entities/repository/domain/model/repository";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

export const isReadOnlyRepository = (schema: ModelSchema): boolean =>
  isOfKind(READONLY_REPOSITORY_KIND, schema);
