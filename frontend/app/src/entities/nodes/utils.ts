import { constructPathForIpam } from "@/entities/ipam/common/utils";
import {
  IPAM_QSP,
  IPAM_ROUTE,
  IP_ADDRESS_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { constructPath, overrideQueryParams } from "@/shared/api/rest/fetch";

export const getObjectDetailsUrl = (
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

  const { schema, isGeneric } = getSchema(objectKind);
  if (!schema) {
    const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
    return constructPath(path, overrideParams);
  }

  if (!isGeneric) {
    const inheritFrom = schema.inherit_from;

    if (inheritFrom?.includes(IP_PREFIX_GENERIC) || inheritFrom?.includes(IP_ADDRESS_GENERIC)) {
      return constructPathForIpam(`/ipam/${schema.kind}/${objectId ?? ""}`, overrideParams);
    }

    if (inheritFrom?.includes(RESOURCE_GENERIC_KIND)) {
      return constructPathForIpam(`/resource-manager/${objectId ?? ""}`, overrideParams);
    }
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
