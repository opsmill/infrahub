import { IP_PREFIX_POOL } from "@/entities/resource-manager/constants";

/**
 * Build the `from_pool` payload for a pending pool allocation, keeping only the fields
 * the API accepts. The prefix length is included only when the user entered a concrete
 * number: the nested prefix-length field registers an `undefined` value when untouched,
 * and serializing that as `undefined` is invalid GraphQL.
 *
 * The from-pool input names the prefix length differently per pool kind: an IP address
 * pool takes `prefixlen` (the new address's mask), an IP prefix pool takes `size` (the
 * carved-out subnet's prefix length). The value model stores it as `prefixlen` either
 * way; this maps it to the field the pool's input expects.
 */
export const buildFromPoolPayload = (
  fromPool: { id: string; prefixlen?: number | null },
  poolKind?: string
): { id: string; prefixlen?: number; size?: number } => {
  const { id, prefixlen } = fromPool;
  if (typeof prefixlen !== "number") {
    return { id };
  }
  return poolKind === IP_PREFIX_POOL ? { id, size: prefixlen } : { id, prefixlen };
};
