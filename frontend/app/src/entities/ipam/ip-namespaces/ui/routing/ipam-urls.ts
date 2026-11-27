import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";
import { QSP } from "@/shared/config/qsp";

export function constructPathForIpam(path: string, overrideParams?: overrideQueryParams[]): string {
  return constructPath(path, overrideParams, [QSP.IPAM_NAMESPACE, QSP.KIND]);
}

export interface IpamNamespaceLink {
  id: string;
  isDefault: boolean;
}

// the IPAM page reads the default namespace from the absence of the parameter
export function getIpamNamespaceUrl({ id, isDefault }: IpamNamespaceLink): string {
  return constructPathForIpam("/ipam", [
    isDefault
      ? { name: QSP.IPAM_NAMESPACE, exclude: true }
      : { name: QSP.IPAM_NAMESPACE, value: id },
  ]);
}
