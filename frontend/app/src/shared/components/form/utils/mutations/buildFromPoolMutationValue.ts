import { IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

export type FromPoolPayload = {
  id: string;
  prefixlen?: number;
  size?: number;
  address_type?: string;
  prefix_type?: string;
};

/**
 * Build the `from_pool` payload for a pending pool allocation, keeping only the fields
 * the API accepts. An override is included only when the user supplied it: the nested fields
 * register `undefined` when untouched, which is invalid GraphQL.
 *
 * Both overrides are named per pool kind — an address pool takes `prefixlen`/`address_type`, a
 * prefix pool takes `size`/`prefix_type` — and an unrecognized kind falls back to the former.
 */
export const buildFromPoolPayload = (
  fromPool: { id: string; prefixLength?: number | null; allocatedKind?: string | null },
  poolKind?: string
): FromPoolPayload => {
  const { id, prefixLength, allocatedKind } = fromPool;
  const isPrefixPool = poolKind === IP_PREFIX_POOL;
  const payload: FromPoolPayload = { id };

  if (typeof prefixLength === "number") {
    if (isPrefixPool) {
      payload.size = prefixLength;
    } else {
      payload.prefixlen = prefixLength;
    }
  }

  if (allocatedKind) {
    if (isPrefixPool) {
      payload.prefix_type = allocatedKind;
    } else {
      payload.address_type = allocatedKind;
    }
  }

  return payload;
};
