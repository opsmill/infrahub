import { Icon } from "@iconify-icon/react";
import React from "react";
import { Collection } from "react-aria-components";

import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@/shared/components/aria/tree";
import { Row } from "@/shared/components/container";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { useGetIpamTreeNodesByParent } from "@/entities/ipam/ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query";
import type { IpamTreeNode } from "@/entities/ipam/ipam-tree/types";
import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/domain/get-object-ancestors.query";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { getSchemaIcon } from "@/entities/schema/utils/get-schema-icon";

export interface IpamTreeProps {
  className?: string;
  currentNodeId?: string;
  search?: string;
}

export function IpamTree({ className, currentNodeId, search }: IpamTreeProps) {
  const [initialNodeId] = React.useState(currentNodeId);
  const { currentIpNamespace } = useCurrentIpNamespace();

  // Load ancestors if currentNodeId is provided
  const { data: ancestorsData, isPending: isPendingGetAncestors } = useGetObjectAncestors(
    {
      objectKind: IP_PREFIX_GENERIC,
      objectId: initialNodeId!,
    },
    {
      enabled: !!initialNodeId,
    }
  );

  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useGetIpamTreeNodesByParent({
      namespaceId: currentIpNamespace.id,
      parentObjectId: null,
      search: search || undefined,
    });

  if (isPending || (initialNodeId && isPendingGetAncestors)) {
    return <LoadingIndicator className="py-2" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const items = data.pages.flat();

  const defaultExpandedKeys = ancestorsData
    ? ancestorsData
        .filter((ancestor) => ancestor.id !== currentNodeId)
        .map((ancestor) => (ancestor.parent.node?.id ?? null) + ancestor.id)
    : undefined;

  return (
    <Tree
      aria-label="IPAM tree"
      defaultExpandedKeys={defaultExpandedKeys}
      renderEmptyState={() => <Row className="justify-center py-2 text-gray-600">No ip prefix</Row>}
      className={className}
    >
      <Collection items={items} dependencies={[currentNodeId]}>
        {(node) => (
          <IpamTreeItem
            parentTreeNodeId={null}
            node={node}
            namespaceId={currentIpNamespace.id}
            currentNodeId={currentNodeId}
            defaultExpandedKeys={defaultExpandedKeys}
          />
        )}
      </Collection>

      {hasNextPage && <TreeItemLoader isLoading={isFetchingNextPage} onLoadMore={fetchNextPage} />}
    </Tree>
  );
}

interface IpamTreeItemProps {
  parentTreeNodeId: string | null;
  node: IpamTreeNode;
  namespaceId: string;
  currentNodeId?: string;
  defaultExpandedKeys?: string[];
}

function IpamTreeItem({
  parentTreeNodeId,
  node,
  namespaceId,
  currentNodeId,
  defaultExpandedKeys,
}: IpamTreeItemProps) {
  const descendantsCount = node.descendants.count;
  const hasChildren = descendantsCount > 0;
  const treeItemId = parentTreeNodeId + node.id;
  const [isExpanded, setIsExpanded] = React.useState<boolean>(
    !!defaultExpandedKeys?.some((key) => key === treeItemId)
  );

  const { data, fetchNextPage, isFetchingNextPage, isPending, hasNextPage } =
    useGetIpamTreeNodesByParent(
      {
        namespaceId,
        parentObjectId: node.id,
      },
      { enabled: isExpanded && hasChildren }
    );

  const { schema: nodeSchema } = useSchema(node.__typename);
  const nodeLabel = getNodeLabel(node);
  const childrenNodes = data?.pages.flat() ?? [];

  return (
    <TreeItem
      id={treeItemId}
      textValue={nodeLabel}
      href={getObjectDetailsUrl(node.__typename, node.id)}
      className={classNames(currentNodeId === node.id && "bg-neutral-100")}
    >
      <TreeItemContent onExpandedChange={() => setIsExpanded((prev) => !prev)}>
        <Icon icon={getSchemaIcon(nodeSchema)} className="mr-2" />
        <span className="truncate">{nodeLabel}</span>
        {descendantsCount > 0 && <Badge className="mr-1 ml-auto">{descendantsCount}</Badge>}
      </TreeItemContent>

      {hasChildren && (
        <>
          <Collection items={childrenNodes} dependencies={[currentNodeId]}>
            {(childNode) => (
              <IpamTreeItem
                parentTreeNodeId={node.id}
                node={childNode}
                namespaceId={namespaceId}
                currentNodeId={currentNodeId}
                defaultExpandedKeys={defaultExpandedKeys}
              />
            )}
          </Collection>

          {(isPending || hasNextPage) && (
            <TreeItemLoader
              isLoading={isPending || isFetchingNextPage}
              onLoadMore={fetchNextPage}
            />
          )}
        </>
      )}
    </TreeItem>
  );
}
