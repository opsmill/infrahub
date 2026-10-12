import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

const NUMBER_POOL_PRESERVED_QSP = [
  QSP.IPAM_NAMESPACE,
  QSP.KIND,
  QSP.POOL_ALLOCATION_BRANCH,
  QSP.POOL_ALLOCATION_SOURCE,
];

export function getNumberPoolRangeUrl(poolId: string, rangeId?: string) {
  const path = rangeId
    ? `/resource-manager/${poolId}/ranges/${rangeId}`
    : `/resource-manager/${poolId}`;
  return constructPath(path, undefined, NUMBER_POOL_PRESERVED_QSP);
}
