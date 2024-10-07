import { constructPathForIpam } from "@/screens/ipam/common/utils";
import {
  IPAM_QSP,
  IPAM_ROUTE,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/screens/ipam/constants";
import { RESOURCE_GENERIC_KIND } from "@/screens/resource-manager/constants";
import { store } from "@/state";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { isGeneric } from "@/utils/common";
import { constructPath, overrideQueryParams } from "./fetch";

const regex = /^Related/; // starts with Related

export const getObjectDetailsUrl = (nodeId: string, nodeType: string): string => {
  const peerKind: string = nodeType?.replace(regex, "");

  return `/objects/${peerKind}/${nodeId}`;
};

export const getObjectDetailsUrl2 = (
  objectKind: string,
  objectId?: string,
  overrideParams?: overrideQueryParams[]
) => {
  if (objectKind === IP_PREFIX_GENERIC) {
    return constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${objectId}`, overrideParams);
  }

  if (objectKind === IP_ADDRESS_GENERIC) {
    return constructPathForIpam(`${IPAM_ROUTE.ADDRESSES}/${objectId}`, [
      { name: IPAM_QSP.TAB, value: "ip-details" },
      ...(overrideParams ?? []),
    ]);
  }

  const nodes = store.get(schemaState);
  const generics = store.get(genericsState);
  const profiles = store.get(profilesAtom);
  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);
  if (!schema) return "#";

  if (!isGeneric(schema)) {
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

    if (inheritFrom?.includes(RESOURCE_GENERIC_KIND)) {
      return constructPathForIpam(`/resource-manager/${objectId}`, overrideParams);
    }
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
