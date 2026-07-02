import { BreadcrumbItem } from "@infrahub/ui";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import type { ModelSchema } from "@/entities/schema/domain/model/types";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

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
