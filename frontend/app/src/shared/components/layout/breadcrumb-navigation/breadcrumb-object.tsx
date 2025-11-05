import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { NodeRelationshipOne } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface BreadcrumbObjectProps {
  objectSchema: ModelSchema;
  objectId: string;
}

export function BreadcrumbObject({ objectSchema, objectId }: BreadcrumbObjectProps) {
  const { isPending, error, data } = useGetObject({ objectSchema, objectId });

  if (isPending || error) {
    return <BreadcrumbItemSchema schema={objectSchema} />;
  }

  const parentRelationship = objectSchema.relationships?.find((rel) => rel.kind === "Parent");
  const parentNode = parentRelationship
    ? (data[parentRelationship.name] as NodeRelationshipOne | undefined)?.node
    : null;

  return (
    <>
      {parentNode && (
        <>
          <BreadcrumbItemObject node={parentNode} />
          <BreadcrumbSeparator />
        </>
      )}
      <BreadcrumbItemObject
        node={data}
        parentId={parentNode?.id}
        parentRelationshipSchema={parentRelationship}
      />
    </>
  );
}
