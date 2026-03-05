import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export function isPoolSchema(schema: ModelSchema | null): boolean {
  return (
    !!schema && !isGenericSchema(schema) && !!schema.inherit_from?.includes(RESOURCE_GENERIC_KIND)
  );
}
