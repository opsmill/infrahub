import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import { useEffect, useState } from "react";
import { addItemsToTree, EMPTY_TREE } from "@/screens/ipam/ipam-tree/utils";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { DiffNode } from "@/screens/diff/node-diff/types";
import { useLocation, useNavigate } from "react-router-dom";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";
import { useSchema } from "@/hooks/useSchema";
import { Icon } from "@iconify-icon/react";
import NoDataFound from "../errors/no-data-found";

interface DiffTreeProps extends Omit<TreeProps, "data"> {
  nodes: Array<DiffNode>;
  emptyMessage?: string;
}

export default function DiffTree({ nodes, loading, emptyMessage, ...props }: DiffTreeProps) {
  const [treeData, setTreeData] = useState<TreeProps["data"]>(EMPTY_TREE);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    const formattedNodes = nodes.reduce((acc, node) => {
      const newNode = {
        id: node.uuid,
        name: node.label,
        parent: TREE_ROOT_ID as string,
        children: acc.filter(({ parent }) => parent === node.uuid).map(({ id }) => id),
        metadata: {
          kind: node.kind, // for icon on tree item
          uuid: node.uuid, // for url
          status: node.status, // for icon color
          containsConflicts: node.contains_conflict, // for icon conflicts
        },
      };

      if (node.parent) {
        const { uuid: parentUUID, relationship_name: parentRelationshipName } = node.parent;

        const parentNodeId = parentUUID + parentRelationshipName;
        const newNodeWithParent = {
          ...newNode,
          parent: parentNodeId,
        };

        const parentOfNewNode = acc.find(({ id }) => id === parentNodeId);
        if (parentOfNewNode) {
          parentOfNewNode.children.push(newNodeWithParent.id);
          return [...acc, newNodeWithParent];
        }

        const newParentNode = {
          id: parentNodeId,
          name: parentRelationshipName ?? "",
          parent: parentUUID,
          children: [newNode.id],
          metadata: {
            kind: node.parent.kind, // for icon on tree item
          },
        };

        return [...acc, newNode, newParentNode];
      }

      return [...acc, newNode];
    }, [] as TreeProps["data"]);

    setTreeData(addItemsToTree(EMPTY_TREE, generateRootCategoryNodeForDiffTree(formattedNodes)));
  }, [nodes]);

  if (treeData.length <= 1) return <NoDataFound message={emptyMessage ?? "No data to display."} />;

  return (
    <Tree
      itemContent={DiffTreeItem}
      propagateSelectUpwards={false}
      defaultExpandedIds={treeData
        .filter(({ parent }) => parent === TREE_ROOT_ID)
        .map(({ id }) => id)}
      loading={loading}
      data={treeData}
      onNodeSelect={({ element }) => {
        navigate({
          ...location,
          hash: element?.metadata?.uuid as string | undefined,
        });
      }}
      {...props}
    />
  );
}

const DiffTreeItem = ({ element }: TreeItemProps) => {
  const diffNode = element.metadata as DiffNode | undefined;
  const { schema } = useSchema(diffNode?.kind);

  // On diff tree, root tree item represents the model schema's name,
  // providing a clear visual representation of the schema in the tree structure.
  if (schema && element.parent === TREE_ROOT_ID) {
    return (
      <div className={"flex items-center gap-2 text-gray-800"} data-testid="hierarchical-tree-item">
        <Icon icon={schema.icon as string} />
        <span className="whitespace-nowrap">{schema.label}</span>
      </div>
    );
  }

  return (
    <a
      href={"#" + diffNode?.uuid}
      tabIndex={-1}
      className="flex items-center gap-2 text-gray-800"
      data-testid="hierarchical-tree-item">
      <DiffBadge
        status={element.metadata?.status as string}
        hasConflicts={!!element.metadata?.containsConflicts}
        icon={schema?.icon ?? undefined}
      />

      <span className="whitespace-nowrap">{element.name}</span>
    </a>
  );
};

export const generateRootCategoryNodeForDiffTree = (
  diffTreeNodes: TreeProps["data"]
): TreeProps["data"] => {
  return diffTreeNodes.reduce((acc, node) => {
    const nodeKind = node.metadata?.kind as string | undefined;
    if (node.parent !== TREE_ROOT_ID || !nodeKind) return [...acc, node];

    const nodeUpdated = {
      ...node,
      parent: nodeKind,
    };

    const existingRootCategoryNode = acc.find(({ id }) => id === nodeKind);

    if (existingRootCategoryNode) {
      const rootCategoryNodeUpdated = {
        ...existingRootCategoryNode,
        children: [...existingRootCategoryNode.children, node.id],
      };

      return acc
        .map((item) => (item.id === existingRootCategoryNode.id ? rootCategoryNodeUpdated : item))
        .concat(nodeUpdated);
    } else {
      const newRootCategoryNode = {
        id: nodeKind,
        name: nodeKind,
        parent: TREE_ROOT_ID,
        children: [node.id],
        isBranch: true,
        metadata: {
          kind: nodeKind,
        },
      };

      return [...acc, newRootCategoryNode, nodeUpdated];
    }
  }, [] as TreeProps["data"]);
};
