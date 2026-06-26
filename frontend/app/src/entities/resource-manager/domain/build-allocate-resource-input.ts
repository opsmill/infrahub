import type { FormFieldValue } from "@/shared/components/form/type";

import type { AllocateResourceInput } from "@/entities/resource-manager/api/allocate-resource-from-api";

/**
 * Assemble the GetResource allocation input for a pool-sourced IP field: the pool id, the
 * created node's attributes, and the optional user-entered prefix length pulled off the
 * field's pending `from_pool` value.
 *
 * Keeps the IPAM form from hand-building the mutation shape. Note this is only needed for
 * the dedicated `...GetResource` allocation mutation that IPAM uses; ordinary forms (e.g. a
 * Device's primary address) allocate through the generic create path, where
 * `getCreateMutationFromFormData`/`buildFromPoolPayload` already handle from-pool fields.
 */
export const buildAllocateResourceInput = ({
  poolId,
  poolFieldValue,
  nodeData,
}: {
  poolId: string;
  poolFieldValue: FormFieldValue["value"];
  nodeData: Record<string, unknown>;
}): AllocateResourceInput => {
  const fromPool =
    poolFieldValue && typeof poolFieldValue === "object" && "from_pool" in poolFieldValue
      ? poolFieldValue.from_pool
      : undefined;

  const input: AllocateResourceInput = { id: poolId, data: nodeData };
  if (typeof fromPool?.prefixLength === "number") {
    input.prefix_length = fromPool.prefixLength;
  }
  return input;
};
