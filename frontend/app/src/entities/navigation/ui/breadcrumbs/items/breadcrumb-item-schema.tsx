import { BreadcrumbItem } from "@infrahub/ui";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function BreadcrumbItemSchema({ kind }: { kind: string }) {
  const { schema } = useSchema(kind);

  if (!schema) return null;

  return <BreadcrumbItem href={getObjectDetailsUrl(kind)}>{schema.label}</BreadcrumbItem>;
}
