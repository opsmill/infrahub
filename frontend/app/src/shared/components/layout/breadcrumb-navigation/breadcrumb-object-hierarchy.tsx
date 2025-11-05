import { keepPreviousData } from "@tanstack/react-query";

import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";
import { BreadcrumbError, BreadcrumbLoading } from "@/shared/components/ui/breadcrumb";

import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
import type { NodeCoreWithParent } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface BreadcrumbObjectProps {
  objectSchema: ModelSchema;
  objectId: string;
}

export function BreadcrumbObjectHierarchy({ objectSchema, objectId }: BreadcrumbObjectProps) {
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
    return <BreadcrumbLoading />;
  }

  if (error) {
    return <BreadcrumbError error={error} />;
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
