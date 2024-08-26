import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import { useEffect, useState } from "react";
import { addItemsToTree, EMPTY_TREE } from "@/screens/ipam/ipam-tree/utils";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { DiffNode } from "@/screens/diff/node-diff/types";
import { useLocation, useNavigate } from "react-router-dom";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";
import { useSchema } from "@/hooks/useSchema";
import { Icon } from "@iconify-icon/react";

interface DiffTreeProps extends Omit<TreeProps, "data"> {
  nodes: Array<DiffNode>;
}

export default function DiffTree({ nodes, loading, ...props }: DiffTreeProps) {
  const [treeData, setTreeData] = useState<TreeProps["data"]>(EMPTY_TREE);
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    let rootModelMap: Record<string, Array<string>> = {};

    const formattedNodes: TreeProps["data"] = nodes.flatMap((node: DiffNode) => {
      const currentModel = rootModelMap[node.kind];
      rootModelMap = {
        ...rootModelMap,
        [node.kind]: currentModel ? [...currentModel, node.uuid] : [node.uuid],
      };

      const newItem = {
        id: node.uuid,
        name: node.label,
        parent: node.kind,
        children: [] as string[],
        isBranch: node.relationships.length > 0,
        metadata: {
          uuid: node.uuid,
          status: node.status,
          containsConflicts: node.contains_conflict,
        },
      };

      const newItemFromRelationships = node.relationships.flatMap((relationship) => {
        const relationshipTreeItem = {
          id: relationship?.name + newItem.id,
          name: relationship?.label,
          parent: newItem.id,
          isBranch: !!relationship?.elements?.length,
          children: [] as string[],
          metadata: {
            uuid: node.uuid,
            containsConflicts: relationship.contains_conflict,
          },
        };

        newItem.children.push(relationshipTreeItem.id);

        const relationshipChildrenTreeItem =
          relationship?.elements?.map((element) => {
            const child = {
              id: newItem.id + element.peer_label + element?.peer_id,
              name: element.peer_label,
              parent: relationshipTreeItem.id,
              isBranch: false,
              children: [],
              metadata: {
                uuid: element?.peer_id,
                status: nodes.find(({ uuid }) => uuid === element.peer_id)?.status,
                containsConflicts: element.contains_conflict,
              },
            };
            relationshipTreeItem.children.push(child.id);

            return child;
          }) ?? [];

        return [relationshipTreeItem, ...relationshipChildrenTreeItem];
      });

      return [newItem, ...newItemFromRelationships];
    });

    const parents = Object.entries(rootModelMap).map(([kind, children]) => {
      return {
        id: kind,
        name: kind,
        parent: TREE_ROOT_ID,
        children,
        isBranch: true,
        metadata: {
          kind,
        },
      };
    });
    setTreeData(addItemsToTree(EMPTY_TREE, [...parents, ...formattedNodes]));
  }, [nodes.length]);

  if (treeData.length <= 1) return null;

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

  if (schema) {
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
        icon
      />

      <span className="whitespace-nowrap">{element.name}</span>
    </a>
  );
};
