import { BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";

export function BreadcrumbItemSchema({ schema }: { schema: ModelSchema }) {
  return <BreadcrumbItem href={getObjectDetailsUrl(schema.kind!)}>{schema.label}</BreadcrumbItem>;
}
