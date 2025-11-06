import { BreadcrumbItem } from "@/shared/components/aria/breadcrumbs";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbItemSchema({ kind }: { kind: string }) {
  const { schema } = useSchema(kind);

  if (!schema) return null;

  return <BreadcrumbItem href={getObjectDetailsUrl(kind)}>{schema.label}</BreadcrumbItem>;
}
