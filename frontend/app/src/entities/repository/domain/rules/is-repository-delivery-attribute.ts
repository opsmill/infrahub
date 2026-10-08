import {
  REPOSITORY_DELIVERY_ATTRIBUTE_NAMES,
  REPOSITORY_KIND,
} from "@/entities/repository/domain/model/repository";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";

/** A branch other than the default one holds a stale copy of these, so generic views must not show them. */
export function isRepositoryDeliveryAttribute(schema: ModelSchema, fieldName: string): boolean {
  return (
    isOfKind(REPOSITORY_KIND, schema) && REPOSITORY_DELIVERY_ATTRIBUTE_NAMES.includes(fieldName)
  );
}
