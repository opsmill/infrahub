import { QSP } from "@/config/qsp";
import { IPAM_QSP } from "@/entities/ipam/constants";
import { constructPath, overrideQueryParams } from "@/shared/api/rest/fetch";

export function constructPathForIpam(path: string, overrideParams?: overrideQueryParams[]): string {
  return constructPath(path, overrideParams, [IPAM_QSP.NAMESPACE, QSP.KIND]);
}
