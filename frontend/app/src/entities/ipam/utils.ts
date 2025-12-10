import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";
import type { Filter } from "@/shared/hooks/useFilters";

import { AVAILABLE_IP_FILTER_NAME, IPAM_QSP } from "@/entities/ipam/constants";

export function constructPathForIpam(path: string, overrideParams?: overrideQueryParams[]): string {
  return constructPath(path, overrideParams, [IPAM_QSP.NAMESPACE, QSP.KIND]);
}

const allowedFiltersWithIpAvailability: Array<Filter["name"]> = [
  "parent__ids",
  "ip_prefix__ids",
  AVAILABLE_IP_FILTER_NAME,
];

export function hasIncompatibleFiltersForIpAvailability(filters: Filter[]) {
  return filters.some(({ name }) => !allowedFiltersWithIpAvailability.includes(name));
}
