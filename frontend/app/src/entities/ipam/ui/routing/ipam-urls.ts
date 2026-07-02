import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

import { IPAM_QSP } from "@/entities/ipam/constants";

export function constructPathForIpam(path: string, overrideParams?: overrideQueryParams[]): string {
  return constructPath(path, overrideParams, [IPAM_QSP.NAMESPACE, QSP.KIND]);
}
