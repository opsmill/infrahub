import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { IP_ADDRESS_POOL, IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import type { ModelSchema } from "@/entities/schema/types";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export function getPoolKindFromSchema(schema: ModelSchema): string | null {
  if (isOfKind(IP_ADDRESS_GENERIC, schema)) {
    return IP_ADDRESS_POOL;
  }

  if (isOfKind(IP_PREFIX_GENERIC, schema)) {
    return IP_PREFIX_POOL;
  }

  return null;
}
