import { constructPath, type overrideQueryParams } from "@/shared/api/rest/fetch";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/ip-namespaces/domain/model/ip-namespace";
import { constructPathForIpam } from "@/entities/ipam/ip-namespaces/ui/routing/ipam-urls";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { RESOURCE_GENERIC_KIND } from "@/entities/resource-manager/domain/model/pool";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

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
