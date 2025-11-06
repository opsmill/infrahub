import { BreadcrumbIpamBase } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-ipam";
import { BreadcrumbObjects } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-objects";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";

export function BreadcrumbIpNamespaces() {
  return (
    <BreadcrumbIpamBase>
      <BreadcrumbItemSchema kind={IP_NAMESPACE_GENERIC} />
      <BreadcrumbObjects />
    </BreadcrumbIpamBase>
  );
}
