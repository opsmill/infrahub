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
 * the API accepts. Each override is included only when the user actually supplied it:
 * the nested override fields register an `undefined` value when untouched, and
 * serializing that as `undefined` is invalid GraphQL.
 *
 * Both overrides are named per pool kind, so each maps to the field that pool's input
 * expects:
 * - prefix length — an IP address pool takes `prefixlen` (the new address's mask), an IP
 *   prefix pool takes `size` (the carved-out subnet's prefix length). The client value
 *   model stores it as `prefixLength` either way.
 * - allocated kind — an IP address pool takes `address_type`, an IP prefix pool takes
 *   `prefix_type`. Set when the relationship peers at a generic (e.g. `BuiltinIPAddress`)
 *   and the user chose which concrete kind to allocate; the client stores it as
 *   `allocatedKind`, distinct from the pool's own `kind`.
 *
 * An unrecognized pool kind falls back to the address-pool field names.
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
