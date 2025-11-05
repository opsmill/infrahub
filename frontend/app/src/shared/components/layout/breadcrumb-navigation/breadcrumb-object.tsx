import { keepPreviousData } from "@tanstack/react-query";

import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";
import { BreadcrumbError, BreadcrumbLoading } from "@/shared/components/ui/breadcrumb";

import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { NodeRelationshipOne } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface BreadcrumbObjectProps {
  objectSchema: ModelSchema;
  objectId: string;
}

export function BreadcrumbObject({ objectSchema, objectId }: BreadcrumbObjectProps) {
  const { isPending, error, data } = useGetObject(
    { objectSchema, objectId },
    {
      placeholderData: keepPreviousData,
    }
  );

  if (isPending) {
    return <BreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
  }

  const parentRelationship = objectSchema.relationships?.find((rel) => rel.kind === "Parent");
  const parentNode = parentRelationship
    ? (data[parentRelationship.name] as NodeRelationshipOne | undefined)?.node
    : null;

  return (
    <>
      {parentNode && <BreadcrumbItemObject node={parentNode} />}
      <BreadcrumbItemObject
        node={data}
        parentId={parentNode?.id}
        parentRelationshipSchema={parentRelationship}
      />
    </>
  );
}
