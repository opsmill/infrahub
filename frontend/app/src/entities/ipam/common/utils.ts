import { IPAM_QSP } from "@/entities/ipam/constants";
import { constructPath, overrideQueryParams } from "@/shared/api/rest/fetch";

export const constructPathForIpam = (path: string, overrideParams?: overrideQueryParams[]) =>
  constructPath(path, overrideParams, [IPAM_QSP.TAB, IPAM_QSP.NAMESPACE]);
