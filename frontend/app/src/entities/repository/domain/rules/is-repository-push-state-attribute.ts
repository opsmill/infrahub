import {
  REPOSITORY_KIND,
  REPOSITORY_PUSH_STATE_ATTRIBUTE_NAMES,
} from "@/entities/repository/domain/model/repository";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

/** Another branch holds an old copy of these, and the push to remote card shows the live value, so generic views must not show them. */
export function isRepositoryPushStateAttribute(schema: ModelSchema, fieldName: string): boolean {
  return (
    isOfKind(REPOSITORY_KIND, schema) && REPOSITORY_PUSH_STATE_ATTRIBUTE_NAMES.includes(fieldName)
  );
}
