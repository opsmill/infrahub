import { useParams } from "react-router";

import { BreadcrumbIpamBase } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-ipam";
import { BreadcrumbObjectDetails } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-object-details";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbIpNamespaces() {
  const { objectKind, objectid } = useParams();
  const { schema } = useSchema(objectKind);

  return (
    <BreadcrumbIpamBase>
      <BreadcrumbItemSchema kind={IP_NAMESPACE_GENERIC} />
      {schema && objectid && <BreadcrumbObjectDetails objectSchema={schema} objectId={objectid} />}
    </BreadcrumbIpamBase>
  );
}
