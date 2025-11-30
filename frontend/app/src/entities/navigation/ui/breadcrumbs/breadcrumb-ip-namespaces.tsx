import { useParams } from "react-router";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { BreadcrumbIpamBase } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-ipam";
import { BreadcrumbObjectDetails } from "@/entities/navigation/ui/breadcrumbs/breadcrumb-object-details";
import { BreadcrumbItemSchema } from "@/entities/navigation/ui/breadcrumbs/items/breadcrumb-item-schema";
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
