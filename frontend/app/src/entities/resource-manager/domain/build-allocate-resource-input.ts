import type { FormFieldValue } from "@/shared/components/form/type";

import type { AllocateResourceInput } from "@/entities/resource-manager/api/allocate-resource-from-api";

/** Build the GetResource input from a pool-sourced IP field (pool id, node attrs, prefix length). */
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
