import { Tree, TreeItem, TreeItemContent, TreeItemLoader } from "@infrahub/ui";
import React from "react";
import { Collection, type Key } from "react-aria-components";

import { Row } from "@/shared/components/container";
import { Icon } from "@/shared/components/display/icon";
import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { classNames } from "@/shared/utils/common";

import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IP_PREFIX_GENERIC } from "@/entities/ipam/ip-prefixes/domain/model/ip-prefix";
import type { IpamTreeNode } from "@/entities/ipam/ipam-tree/domain/model/ipam-tree-node";
import {
  applyIpamTreeExpansionChange,
  deriveIpamTreeExpandedKeys,
  EMPTY_MANUAL_EXPANSION,
  getIpamTreeAncestorKeys,
  getIpamTreeItemId,
  type IpamTreeKey,
} from "@/entities/ipam/ipam-tree/domain/rules/derive-ipam-tree-expanded-keys";
import { useGetIpamTreeNodesByParent } from "@/entities/ipam/ipam-tree/ui/queries/get-ipam-tree-nodes-by-parent.query";
import { useGetObjectAncestors } from "@/entities/nodes/hierarchy/ui/queries/get-object-ancestors.query";
import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { getSchemaIcon } from "@/entities/schema/domain/rules/get-schema-icon";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface IpamTreeProps {
  className?: string;
  currentNodeId?: string;
  search?: string;
}

function toTreeKeys(keys: Set<Key>): Set<IpamTreeKey> {
  return new Set([...keys].map(String));
}

export function IpamTree({ className, currentNodeId, search }: IpamTreeProps) {
  const { currentIpNamespace } = useCurrentIpNamespace();
  const [manualExpansion, setManualExpansion] = React.useState(EMPTY_MANUAL_EXPANSION);

  // The previous path stays open while the next one loads, so in-app navigation never blanks the tree.
  const { data: ancestorsData, isPending: isPendingAncestors } = useGetObjectAncestors(
    {
      objectKind: IP_PREFIX_GENERIC,
      objectId: currentNodeId ?? "",
    },
    {
      enabled: !!currentNodeId,
      placeholderData: (previous) => previous,
    }
  );

  const { data, isPending, error, hasNextPage, fetchNextPage, isFetchingNextPage } =
    useGetIpamTreeNodesByParent({
      namespaceId: currentIpNamespace.id,
      parentObjectId: null,
      search: search || undefined,
    });

  const isWaitingForFirstAncestors = !!currentNodeId && isPendingAncestors && !ancestorsData;

  if (isPending || isWaitingForFirstAncestors) {
    return <LoadingIndicator className="py-2" />;
  }

  if (error) {
    return <ErrorScreen message={error.message} />;
  }

  const items = data.pages.flat();
  const expandedKeys = deriveIpamTreeExpandedKeys(
    getIpamTreeAncestorKeys(ancestorsData, currentNodeId),
    manualExpansion,
    currentNodeId
  );
  // Collections compare dependencies by reference, so a string stands in for the set.
  const expansionSignature = [...expandedKeys].sort().join("|");

  const handleExpandedChange = (nextKeys: Set<Key>) => {
    setManualExpansion((previous) =>
      applyIpamTreeExpansionChange(previous, expandedKeys, toTreeKeys(nextKeys), currentNodeId)
    );
  };

  return (
    <Tree
      aria-label="IPAM tree"
      expandedKeys={expandedKeys}
      onExpandedChange={handleExpandedChange}
      renderEmptyState={() => (
        <Row className="justify-center py-2 text-subtle-muted">No ip prefix</Row>
      )}
      className={className}
    >
      <Collection items={items} dependencies={[currentNodeId, expansionSignature]}>
        {(node) => (
          <IpamTreeItem
            parentTreeNodeId={null}
            node={node}
            namespaceId={currentIpNamespace.id}
            currentNodeId={currentNodeId}
            expandedKeys={expandedKeys}
            expansionSignature={expansionSignature}
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
  expandedKeys: ReadonlySet<IpamTreeKey>;
  expansionSignature: string;
}

function IpamTreeItem({
  parentTreeNodeId,
  node,
  namespaceId,
  currentNodeId,
  expandedKeys,
  expansionSignature,
}: IpamTreeItemProps) {
  const descendantsCount = node.descendants.count;
  const hasChildren = descendantsCount > 0;
  const treeItemId = getIpamTreeItemId(parentTreeNodeId, node.id);
  const isExpanded = expandedKeys.has(treeItemId);

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
      className={classNames(
        currentNodeId === node.id &&
          "bg-selected text-selected-foreground shadow-selected hover:bg-selected-highlight"
      )}
    >
      <TreeItemContent>
        <Icon icon={getSchemaIcon(nodeSchema)} className="mr-2" />
        <span className="truncate">{nodeLabel}</span>
        {descendantsCount > 0 && <Badge className="mr-1 ml-auto">{descendantsCount}</Badge>}
      </TreeItemContent>

      {hasChildren && (
        <>
          <Collection items={childrenNodes} dependencies={[currentNodeId, expansionSignature]}>
            {(childNode) => (
              <IpamTreeItem
                parentTreeNodeId={node.id}
                node={childNode}
                namespaceId={namespaceId}
                currentNodeId={currentNodeId}
                expandedKeys={expandedKeys}
                expansionSignature={expansionSignature}
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
