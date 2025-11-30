import { useParams } from "react-router";

import { BreadcrumbIpamBase } from "@/entities/breadcrumbs/ui/breadcrumb-ipam";
import { BreadcrumbObjectDetails } from "@/entities/breadcrumbs/ui/breadcrumb-object-details";
import { BreadcrumbItemSchema } from "@/entities/breadcrumbs/ui/items/breadcrumb-item-schema";
import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbIpNamespaces() {
  const { objectKind, objectId } = useParams();
  const { schema } = useSchema(objectKind);

  return (
    <BreadcrumbIpamBase>
      <BreadcrumbItemSchema kind={IP_NAMESPACE_GENERIC} />
      {schema && objectId && <BreadcrumbObjectDetails objectSchema={schema} objectId={objectId} />}
    </BreadcrumbIpamBase>
  );
}
