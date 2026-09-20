import type { FormFieldValue } from "@/shared/components/form/type";

import type { AllocateResourceInput } from "@/entities/resource-manager/api/allocate-resource-from-api";
import { IP_PREFIX_POOL } from "@/entities/resource-manager/domain/model/pool";

/**
 * The target kind is named per pool kind (`address_type` vs `prefix_type`); an unrecognized
 * pool kind falls back to the address-pool field name.
 */
export const buildAllocateResourceInput = ({
  poolId,
  poolKind,
  poolFieldValue,
  nodeData,
}: {
  poolId: string;
  poolKind?: string;
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
  if (fromPool?.allocatedKind) {
    if (poolKind === IP_PREFIX_POOL) {
      input.prefix_type = fromPool.allocatedKind;
    } else {
      input.address_type = fromPool.allocatedKind;
    }
  }
  return input;
};
