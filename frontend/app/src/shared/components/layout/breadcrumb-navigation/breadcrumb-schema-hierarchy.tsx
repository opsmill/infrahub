import { BreadcrumbItem } from "@/shared/components/ui/breadcrumb";

import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

export interface BreadcrumbSchemaHierarchicalProps {
  schema: ModelSchema;
}

export function BreadcrumbSchemaHierarchy({ schema }: BreadcrumbSchemaHierarchicalProps) {
  const { schema: parentSchema } = useSchema(
    schema?.relationships?.find((rel) => rel.name === "parent")?.peer
  );

  if (isGenericSchema(schema)) {
    return null;
  }

  return (
    <>
      {parentSchema && <BreadcrumbSchemaHierarchy schema={parentSchema} />}
      <BreadcrumbItem href={getObjectDetailsUrl(schema.kind!)}>{schema.label}</BreadcrumbItem>
    </>
  );
}
