import { BreadcrumbIpamBase } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-ipam";
import { BreadcrumbObjects } from "@/shared/components/layout/breadcrumb-navigation/breadcrumb-objects";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";

import { IP_NAMESPACE_GENERIC } from "@/entities/ipam/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbIpNamespaces() {
  const { schema } = useSchema(IP_NAMESPACE_GENERIC);

  if (!schema) return null;

  return (
    <BreadcrumbIpamBase>
      <BreadcrumbItemSchema schema={schema} />
      <BreadcrumbObjects />
    </BreadcrumbIpamBase>
  );
}
