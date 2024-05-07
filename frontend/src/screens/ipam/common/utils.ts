import { constructPath, overrideQueryParams } from "../../../utils/fetch";
import { IPAM_QSP } from "../constants";

export const constructPathForIpam = (path: string, overrideParams?: overrideQueryParams[]) =>
  constructPath(path, overrideParams, [IPAM_QSP]);
