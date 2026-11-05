import { constructPath } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

const IP_POOL_PRESERVED_QSP = [QSP.IPAM_NAMESPACE, QSP.KIND];

export function getIpPoolResourceUrl(poolId: string, resourceId?: string) {
  const path = resourceId
    ? `/resource-manager/${poolId}/resources/${resourceId}`
    : `/resource-manager/${poolId}`;
  return constructPath(path, undefined, IP_POOL_PRESERVED_QSP);
}
