import { keepPreviousData } from "@tanstack/react-query";

import { BreadcrumbItemError, BreadcrumbItemLoading } from "@/shared/components/aria/breadcrumbs";
import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";

import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
import type { NodeCoreWithParent } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface BreadcrumbObjectDetailsHierarchyProps {
  objectSchema: ModelSchema;
  objectId: string;
}

export function BreadcrumbObjectDetailsHierarchy({
  objectSchema,
  objectId,
}: BreadcrumbObjectDetailsHierarchyProps) {
  const { data, isPending, error } = useGetObjectAncestors(
    {
      objectKind: objectSchema.kind!,
      objectId,
    },
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

  return data.map((ancestor) => (
    <BreadcrumbItemObjectHierarchy key={ancestor.id} node={ancestor} />
  ));
}

function BreadcrumbItemObjectHierarchy({ node }: { node: NodeCoreWithParent }) {
  const { schema } = useSchema(node.__typename);
  const parentRelationshipSchema = schema?.relationships?.find(
    (rel) => rel.kind === "Hierarchy" && rel.name === "parent"
  );

  return (
    <BreadcrumbItemObject
      node={node}
      parentId={node.parent.node?.id}
      parentRelationshipSchema={parentRelationshipSchema}
    />
  );
}
