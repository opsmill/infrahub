import {
  IP_ADDRESS_GENERIC,
  IP_NAMESPACE_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";
import { constructPath, overrideQueryParams } from "@/shared/api/rest/fetch";

export const getObjectDetailsUrl = (
  objectKind: string,
  objectId?: string,
  overrideParams?: overrideQueryParams[]
) => {
  const { schema } = getSchema(objectKind);
  if (!schema) {
    const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
    return constructPath(path, overrideParams);
  }

  if (isOfKind(IP_PREFIX_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}` : "/ipam";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_ADDRESS_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}` : "/ipam/ip_addresses";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_NAMESPACE_GENERIC, schema)) {
    const path = objectId ? `/ipam/namespaces/${objectKind}/${objectId}` : "/ipam/namespaces";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(RESOURCE_GENERIC_KIND, schema)) {
    return constructPathForIpam(`/resource-manager/${objectId ?? ""}`, overrideParams);
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
