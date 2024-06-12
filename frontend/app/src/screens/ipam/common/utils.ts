import { IPAM_QSP } from "@/screens/ipam/constants";
import { constructPath, overrideQueryParams } from "@/utils/fetch";

export const constructPathForIpam = (path: string, overrideParams?: overrideQueryParams[]) =>
  constructPath(path, overrideParams, [IPAM_QSP.TAB, IPAM_QSP.NAMESPACE]);
