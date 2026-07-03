import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

export function constructPathForIpam(path: string, overrideParams?: overrideQueryParams[]): string {
  return constructPath(path, overrideParams, [QSP.IPAM_NAMESPACE, QSP.KIND]);
}
