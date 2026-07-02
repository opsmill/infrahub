import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import type { ModelSchema } from "@/entities/schema/domain/model/types";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";

export function isPoolSchema(schema: ModelSchema | null): boolean {
  return (
    !!schema && !isGenericSchema(schema) && !!schema.inherit_from?.includes(RESOURCE_GENERIC_KIND)
  );
}
