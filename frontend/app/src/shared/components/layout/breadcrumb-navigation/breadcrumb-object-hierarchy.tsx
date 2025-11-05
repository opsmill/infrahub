import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";
import { BreadcrumbItemSchema } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-schema";
import { BreadcrumbSeparator } from "@/shared/components/ui/breadcrumb";

import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
import type { NodeCoreWithParent } from "@/entities/nodes/types";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface BreadcrumbObjectProps {
  schema: ModelSchema;
  objectId: string;
}

export function BreadcrumbObjectHierarchy({ schema, objectId }: BreadcrumbObjectProps) {
  const { data, isPending, error } = useGetObjectAncestors({ objectKind: schema.kind!, objectId });

  if (isPending || error) {
    return <BreadcrumbItemSchema schema={schema} />;
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
    <>
      <BreadcrumbSeparator />
      <BreadcrumbItemObject
        node={node}
        parentId={node.parent.node?.id}
        parentRelationshipSchema={parentRelationshipSchema}
      />
    </>
  );
}
