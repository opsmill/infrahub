import { keepPreviousData } from "@tanstack/react-query";
import { TriangleAlertIcon } from "lucide-react";

import { INFRAHUB_DOC_LOCAL } from "@/config/config";

import {
  BreadcrumbItem,
  BreadcrumbItemError,
  BreadcrumbItemLoading,
} from "@/shared/components/aria/breadcrumbs";
import { BreadcrumbItemObject } from "@/shared/components/layout/breadcrumb-navigation/items/breadcrumb-item-object";
import { Tooltip } from "@/shared/components/ui/tooltip";

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

  const hasTopLevelNode = data.some((node) => !node.parent.node);

  return (
    <>
      {!hasTopLevelNode && (
        <Tooltip
          enabled
          content={
            <div className="max-w-xs">
              <p className="mb-2 font-semibold">Hierarchy depth limit reached</p>
              <p>
                The complete hierarchy cannot be displayed because the maximum search depth has
                been reached. Click to learn more about configuring{" "}
                <code className="bg-gray-700">INFRAHUB_DB_MAX_DEPTH_SEARCH_HIERARCHY</code>.
              </p>
            </div>
          }
        >
          <BreadcrumbItem
            href={`${INFRAHUB_DOC_LOCAL}/reference/configuration#database`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-amber-600"
          >
            <TriangleAlertIcon className="size-4" /> Depth limit reached
          </BreadcrumbItem>
        </Tooltip>
      )}

      {data.map((ancestor) => (
        <BreadcrumbItemObjectHierarchy key={ancestor.id} node={ancestor} />
      ))}
    </>
  );
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
