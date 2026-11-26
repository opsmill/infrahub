import { parseAsStringLiteral, useQueryState } from "nuqs";

import { QSP } from "@/shared/config/qsp";

import {
  NUMBER_POOL_PROVENANCES,
  type NumberPoolAllocationFilters,
} from "@/entities/resource-manager/domain/model/number-pool";

export function useNumberPoolAllocationFilters() {
  const [branch, setBranch] = useQueryState(QSP.POOL_ALLOCATION_BRANCH);
  const [provenance, setProvenance] = useQueryState(
    QSP.POOL_ALLOCATION_SOURCE,
    parseAsStringLiteral(NUMBER_POOL_PROVENANCES)
  );

  const filters: NumberPoolAllocationFilters = {
    branch: branch ?? undefined,
    provenance: provenance ?? undefined,
  };

  const setFilters = (next: NumberPoolAllocationFilters) => {
    setBranch(next.branch ?? null);
    setProvenance(next.provenance ?? null);
  };

  return [filters, setFilters] as const;
}
