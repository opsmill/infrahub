import { keepPreviousData } from "@tanstack/react-query";

import { BreadcrumbItemError, BreadcrumbItemLoading } from "@/shared/components/aria/breadcrumbs";

import { BreadcrumbItemObject } from "@/entities/navigation/ui/breadcrumbs/items/breadcrumb-item-object";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import type { NodeRelationshipOne } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";

interface BreadcrumbObjectDetailsProps {
  objectSchema: ModelSchema;
  objectId: string;
  autocompleteObjectKind?: string;
}

export function BreadcrumbObjectDetails({
  autocompleteObjectKind,
  objectSchema,
  objectId,
}: BreadcrumbObjectDetailsProps) {
  const { isPending, error, data } = useGetObject(
    { objectSchema, objectId },
    {
      placeholderData: keepPreviousData,
    }
  );

  if (isPending) {
    return <BreadcrumbItemLoading />;
  }

  if (error) {
    return <BreadcrumbItemError error={error} />;
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
        autocompleteObjectKind={autocompleteObjectKind}
        parentId={parentNode?.id}
        parentRelationshipSchema={parentRelationship}
      />
    </>
  );
}
