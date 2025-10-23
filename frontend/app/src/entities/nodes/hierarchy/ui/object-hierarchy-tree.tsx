import { Icon } from "@iconify-icon/react";
import { ListTreeIcon } from "lucide-react";
import { Collection } from "react-aria-components";

import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@/shared/components/aria/tree";
import { Col, Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { classNames } from "@/shared/utils/common";

import { useGetTreeNodesByParent } from "@/entities/nodes/hierarchy/domain/get-tree-nodes-by-parent.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeCoreWithChildrenCount } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export interface ObjectHierarchyTreeProps {
  treeSchema: ModelSchema;
  currentNodeId?: string;
}

export function ObjectHierarchyTree({ treeSchema, currentNodeId }: ObjectHierarchyTreeProps) {
  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useGetTreeNodesByParent({
      objectKind: treeSchema.kind!,
      parentObjectId: null, // to query for top-level nodes
    });

  if (isPending) {
    return <LoadingIndicator />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const items = data.pages.flat();

  if (items.length === 0) {
    return (
      <Col className="items-center justify-center py-8">
        <ListTreeIcon className="size-4 text-gray-600" />
        <p className="font-medium text-lg">No {treeSchema.label} found</p>
        <p className="text-center text-gray-400 text-sm">
          Create objects and establish parent-child relationships to build your hierarchy
        </p>
      </Col>
    );
  }

  return (
    <Tree
      aria-label="Hierarchy tree"
      selectedKeys={currentNodeId ? [currentNodeId] : undefined}
      renderEmptyState={() => <Row className="justify-center py-2 text-gray-600">No item</Row>}
    >
      <Collection items={items} dependencies={[currentNodeId]}>
        {(node) => (
          <ObjectTreeItem
            node={node}
            treeObjectKind={treeSchema.kind!}
            currentNodeId={currentNodeId}
          />
        )}
      </Collection>

      {hasNextPage && <TreeItemLoader isLoading={isFetchingNextPage} onLoadMore={fetchNextPage} />}
    </Tree>
  );
}

export interface ObjectTreeItemProps {
  node: NodeCoreWithChildrenCount;
  treeObjectKind: string;
  currentNodeId?: string;
}
export function ObjectTreeItem({ node, treeObjectKind, currentNodeId }: ObjectTreeItemProps) {
  const { data, fetchNextPage, isFetchingNextPage, isPending, hasNextPage } =
    useGetTreeNodesByParent(
      {
        objectKind: treeObjectKind,
        parentObjectId: node.id,
      },
      { enabled: false }
    );

  const { schema: nodeSchema } = useSchema(node.__typename);
  const nodeLabel = getNodeLabel(node);
  const childrenNode = data?.pages.flat() ?? [];

  return (
    <TreeItem
      textValue={node.id}
      href={getObjectDetailsUrl(node.__typename, node.id)}
      className={classNames(currentNodeId === node.id && "bg-neutral-100")}
    >
      <TreeItemContent>
        <Icon icon={getSchemaIcon(nodeSchema)} className="mr-2" />
        <span className="truncate">{nodeLabel}</span>
      </TreeItemContent>

      {node.children.count > 0 && (
        <>
          <Collection items={childrenNode} dependencies={[currentNodeId]}>
            {(childNode) => (
              <ObjectTreeItem
                node={childNode}
                treeObjectKind={treeObjectKind}
                currentNodeId={currentNodeId}
              />
            )}
          </Collection>

          {(isPending || hasNextPage) && (
            <TreeItemLoader isLoading={isFetchingNextPage} onLoadMore={fetchNextPage} />
          )}
        </>
      )}
    </TreeItem>
  );
}
