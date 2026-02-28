import { ArrowLeftIcon } from "lucide-react";
import React from "react";

import { Tree } from "@/shared/components/aria/tree";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Button } from "@/shared/components/ui/button";

import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/ui/queries/get-object-ancestors.query";
import {
  ObjectHierarchyTree,
  type ObjectHierarchyTreeProps,
  ObjectTreeItem,
} from "@/entities/nodes/hierarchy/ui/object-hierarchy-tree";

interface ObjectHierarchyTreeLiteProps extends ObjectHierarchyTreeProps {
  initialId: string;
}

export function ObjectHierarchyTreeLite({
  treeSchema,
  currentNodeId,
  initialId,
}: ObjectHierarchyTreeLiteProps) {
  const [displayFullTree, setDisplayFullTree] = React.useState(false);
  const { data, isPending, error } = useGetObjectAncestors({
    objectKind: treeSchema.kind!,
    objectId: initialId,
  });

  if (isPending) {
    return <LoadingIndicator />;
  }

  const currentSelectedNode = data?.at(-1);
  const parentId = currentSelectedNode?.parent?.node?.id;
  const parentNode = parentId && data ? data.find((node) => node.id === parentId) : undefined;

  // Fall back to full tree if there's an error (e.g., initial node was deleted),
  // no parent node found, or user requested full tree
  if (error || !parentNode || displayFullTree) {
    return (
      <ObjectHierarchyTree
        treeSchema={treeSchema}
        currentNodeId={currentNodeId}
        defaultExpandedIds={data?.length ? data.map((node) => node.id) : undefined}
      />
    );
  }

  return (
    <>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setDisplayFullTree(true)}
        className="w-full justify-start gap-2 px-2.5 text-custom-blue-800"
      >
        <ArrowLeftIcon className="size-3.5" /> Back
      </Button>

      <Tree
        aria-label="Hierarchy tree lite"
        defaultExpandedKeys={parentNode ? [parentNode.id] : undefined}
      >
        <ObjectTreeItem
          node={parentNode}
          defaultExpanded
          hasChildren
          treeObjectKind={treeSchema.kind!}
          currentNodeId={currentNodeId}
        />
      </Tree>
    </>
  );
}
