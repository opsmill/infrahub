import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

import {
  IP_ADDRESS_GENERIC,
  IP_NAMESPACE_GENERIC,
  IP_PREFIX_GENERIC,
} from "@/entities/ipam/constants";
import { constructPathForIpam } from "@/entities/ipam/utils";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/constants";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/constants";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const getObjectDetailsUrl = (
  objectKind: string,
  objectId?: string,
  overrideParams?: overrideQueryParams[],
  tabSegment?: string
) => {
  const tab = tabSegment ? `/${tabSegment}` : "";
  const { schema } = getSchema(objectKind);
  if (!schema) {
    const path = objectId ? `/objects/${objectKind}/${objectId}${tab}` : `/objects/${objectKind}`;
    return constructPath(path, overrideParams);
  }

  if (isOfKind(IP_PREFIX_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}${tab}` : "/ipam";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_ADDRESS_GENERIC, schema)) {
    const path = objectId ? `/ipam/${objectKind}/${objectId}${tab}` : "/ipam/ip_addresses";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(IP_NAMESPACE_GENERIC, schema)) {
    const path = objectId ? `/ipam/namespaces/${objectKind}/${objectId}${tab}` : "/ipam/namespaces";
    return constructPathForIpam(path, overrideParams);
  }

  if (isOfKind(RESOURCE_GENERIC_KIND, schema)) {
    return constructPathForIpam(`/resource-manager/${objectId ?? ""}`, overrideParams);
  }

  if (isOfKind(PROPOSED_CHANGE_OBJECT, schema)) {
    const path = objectId ? `/proposed-changes/${objectId}${tab}` : "/proposed-changes";
    return constructPathForIpam(path, overrideParams);
  }

  const path = objectId ? `/objects/${objectKind}/${objectId}${tab}` : `/objects/${objectKind}`;
  return constructPath(path, overrideParams);
};
