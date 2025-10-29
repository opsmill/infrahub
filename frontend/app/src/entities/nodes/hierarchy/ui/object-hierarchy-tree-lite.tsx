import { ArrowLeftIcon } from "lucide-react";
import React from "react";

import { Tree } from "@/shared/components/aria/tree";
import { Button } from "@/shared/components/buttons/button-primitive";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
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

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const currentSelectedNode = data.at(-1);
  const parentNode = data.find((node) => node.id === currentSelectedNode?.parent.node?.id);

  if (!parentNode || displayFullTree) {
    return (
      <ObjectHierarchyTree
        treeSchema={treeSchema}
        currentNodeId={currentNodeId}
        defaultExpandedIds={data?.length > 1 ? data.map((node) => node.id) : undefined}
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
          hasChildren
          treeObjectKind={treeSchema.kind!}
          currentNodeId={currentNodeId}
        />
      </Tree>
    </>
  );
}
