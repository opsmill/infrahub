import { constructPathForIpam } from "@/entities/ipam/common/utils";
import {
  IPAM_QSP,
  IPAM_ROUTE,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { genericsState, profilesAtom, schemaState } from "@/entities/schema/schema.atom";
import { isGenericSchema } from "@/entities/schema/utils";
import { store } from "@/shared/stores";
import { constructPath, overrideQueryParams } from "../../shared/api/rest/fetch";

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
    return constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${objectId ?? ""}`, overrideParams);
  }

  if (objectKind === IP_ADDRESS_GENERIC) {
    return constructPathForIpam(`${IPAM_ROUTE.ADDRESSES}/${objectId ?? ""}`, [
      { name: IPAM_QSP.TAB, value: "ip-details" },
      ...(overrideParams ?? []),
    ]);
  }

  const nodes = store.get(schemaState);
  const generics = store.get(genericsState);
  const profiles = store.get(profilesAtom);
  const schema = [...nodes, ...generics, ...profiles].find(({ kind }) => kind === objectKind);
  if (!schema) return "#";

  if (!isGenericSchema(schema)) {
    const inheritFrom = schema.inherit_from;

    if (inheritFrom?.includes(IP_PREFIX_GENERIC)) {
      return constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${objectId ?? ""}`, overrideParams);
    }

    if (inheritFrom?.includes(IP_ADDRESS_GENERIC)) {
      return constructPathForIpam(`${IPAM_ROUTE.ADDRESSES}/${objectId ?? ""}`, [
        { name: IPAM_QSP.TAB, value: "ip-details" },
        ...(overrideParams ?? []),
      ]);
    }

    if (inheritFrom?.includes(RESOURCE_GENERIC_KIND)) {
      return constructPathForIpam(`/resource-manager/${objectId ?? ""}`, overrideParams);
    }
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
