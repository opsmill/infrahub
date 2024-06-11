import { constructPathForIpam } from "@/screens/ipam/common/utils";
import {
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
  IPAM_QSP,
  IPAM_ROUTE,
} from "@/screens/ipam/constants";
import { store } from "@/state";
import { schemaState } from "@/state/atoms/schema.atom";
import { constructPath, overrideQueryParams } from "./fetch";

const regex = /^Related/; // starts with Related

export const getObjectDetailsUrl = (nodeId: string, nodeType: string): string => {
  const peerKind: string = nodeType?.replace(regex, "");

  return `/objects/${peerKind}/${nodeId}`;
};

export const resolve = (path: string, object: any, separator: string = ".") => {
  const properties: Array<any> = Array.isArray(path) ? path : path.split(separator);

  return properties.reduce((prev: any, curr: any) => prev?.[curr], object);
};

export const getObjectDetailsUrl2 = (
  objectKind: string,
  objectId: string,
  overrideParams?: overrideQueryParams[]
) => {
  const nodes = store.get(schemaState);
  const schema = nodes.find(({ kind }) => kind === objectKind);
  if (!schema) return constructPath("/", overrideParams);

  const inheritFrom = schema.inherit_from;

  if (inheritFrom?.includes(IP_PREFIX_GENERIC)) {
    return constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${objectId}`, overrideParams);
  }

  if (inheritFrom?.includes(IP_ADDRESS_GENERIC)) {
    return constructPathForIpam(`${IPAM_ROUTE.ADDRESSES}/${objectId}`, [
      { name: IPAM_QSP.TAB, value: "ip-details" },
      ...(overrideParams ?? []),
    ]);
  }

  return constructPath(`/objects/${objectKind}/${objectId}`, overrideParams);
};
