import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import type { NumberPoolDivisionValue } from "@/entities/resource-manager/domain/model/number-pool";

const NUMBER_POOL_PRESERVED_QSP = [
  QSP.IPAM_NAMESPACE,
  QSP.KIND,
  QSP.POOL_ALLOCATION_BRANCH,
  QSP.POOL_ALLOCATION_SOURCE,
  QSP.ALLOCATION_SCOPE,
];

export function getNumberPoolRangeUrl(poolId: string, rangeId?: string) {
  const path = rangeId
    ? `/resource-manager/${poolId}/ranges/${rangeId}`
    : `/resource-manager/${poolId}`;
  return constructPath(path, undefined, NUMBER_POOL_PRESERVED_QSP);
}

export function getNumberPoolDivisionUrl(poolId: string, values: NumberPoolDivisionValue[]) {
  return constructPath(
    `/resource-manager/${poolId}`,
    [{ name: QSP.ALLOCATION_SCOPE, value: JSON.stringify(values) }],
    NUMBER_POOL_PRESERVED_QSP
  );
}

export function getNumberPoolDivisionsUrl(poolId: string) {
  return constructPath(
    `/resource-manager/${poolId}`,
    [{ name: QSP.ALLOCATION_SCOPE, exclude: true }],
    NUMBER_POOL_PRESERVED_QSP
  );
}
