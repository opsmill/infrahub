import { TreeSkeleton } from "@/components/ui/tree-sheleton";
import useQuery from "@/hooks/useQuery";
import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import { useState } from "react";
import { addItemsToTree, EMPTY_TREE } from "@/screens/ipam/ipam-tree/utils";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";
import { getProposedChangesDiffTree } from "@/graphql/queries/proposed-changes/getProposedChangesDiffTree";
import { DiffBadge } from "@/screens/diff/node-diff/utils";
import { DiffNode } from "@/screens/diff/node-diff/types";
import { useLocation, useNavigate } from "react-router-dom";

interface DiffTreeProps extends Omit<TreeProps, "data"> {
  branchName?: string;
}

export default function DiffTree({ branchName, ...props }: DiffTreeProps) {
  const [treeData, setTreeData] = useState<TreeProps["data"]>(EMPTY_TREE);
  const location = useLocation();
  const navigate = useNavigate();

  const { loading, error } = useQuery(getProposedChangesDiffTree, {
    variables: {
      branch: branchName,
    },
    skip: !branchName,
    onCompleted: (data) => {
      const formattedNodes: TreeProps["data"] = data.DiffTree.nodes
        .filter((node: DiffNode) => node.status !== "UNCHANGED")
        .flatMap((node: DiffNode) => {
          const newItem = {
            id: node.uuid,
            name: node.label,
            parent: node.parent?.uuid ?? TREE_ROOT_ID,
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
                    status: element.status,
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

      setTreeData(addItemsToTree(EMPTY_TREE, formattedNodes));
    },
  });

  if (loading) return <TreeSkeleton {...props} />;
  if (error || treeData.length < 2) return null;

  return (
    <Tree
      itemContent={DiffTreeItem}
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

  return (
    <a
      href={"#" + diffNode?.uuid}
      tabIndex={-1}
      className="flex items-center gap-2"
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
