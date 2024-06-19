import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import { atom, useAtom, useAtomValue } from "jotai/index";
import {
  EMPTY_IPAM_TREE,
  getTreeItemAncestors,
  ROOT_TREE_ITEM,
} from "@/screens/ipam/ipam-tree/utils";
import { genericsState, IModelSchema, schemaState } from "@/state/atoms/schema.atom";
import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { useLazyQuery } from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { objectAncestorsQuery } from "@/graphql/queries/objects/getObjectAncestors";
import { IPAM_TREE_ROOT_ID } from "@/screens/ipam/constants";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "@/utils/fetch";
import { NodeId } from "react-accessible-treeview";

export const hierarchicalTreeAtom = atom<TreeProps["data"]>(EMPTY_IPAM_TREE);

export type HierarchicalTreeProps = {
  schema: IModelSchema;
  currentNodeId?: string;
};

const HierarchicalTree = ({ schema, currentNodeId }: HierarchicalTreeProps) => {
  const navigate = useNavigate();
  const [treeData, setTreeData] = useAtom(hierarchicalTreeAtom);
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);

  const [isLoading, setLoading] = useState(true);

  const query = gql(objectAncestorsQuery({ kind: schema.kind, id: currentNodeId }));
  const [getObjectAncestors] = useLazyQuery(query);

  useEffect(() => {
    getObjectAncestors().then(({ data }) => {
      let rootNodeIds: string[] = [];
      const tree = data[schema.kind].edges.map(({ node }, i, array) => {
        const nodeId = node?.id;
        const parentId = node.parent?.node?.id ?? IPAM_TREE_ROOT_ID;

        if (parentId === IPAM_TREE_ROOT_ID) rootNodeIds.push(nodeId);

        return {
          id: node.id,
          name: node.display_label,
          children: array
            .filter(({ node }) => node?.parent?.node?.id === nodeId)
            .map(({ node }) => node?.id),
          parent: parentId,
          isBranch: node.children.count > 0,
          metadata: {
            kind: node.__typename,
          },
        };
      });
      const newTree = [{ ...ROOT_TREE_ITEM, children: rootNodeIds }, ...tree];
      if (currentNodeId) {
        const ancestorIds = getTreeItemAncestors(newTree, currentNodeId).map(({ id }) => id);
        setExpandedIds(ancestorIds);
      }
      setTreeData(newTree);
      setLoading(false);
    });
  }, [currentNodeId]);

  if (isLoading) return null;

  return (
    <Card className="w-full max-w-sm self-start">
      <Tree
        data={treeData}
        itemContent={ObjectTreeItem}
        defaultExpandedIds={expandedIds}
        selectedIds={currentNodeId ? [currentNodeId] : undefined}
        onNodeSelect={({ element, isSelected, isBranch }) => {
          if (!isSelected || isBranch) return;

          const url = constructPath(`/objects/${schema?.kind}/${element.id}`);
          navigate(url);
        }}
      />
    </Card>
  );
};

const ObjectTreeItem = ({ element }: TreeItemProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const schema = [...nodes, ...generics].find(({ kind }) => kind === element.metadata?.kind);
  const url = constructPath(`/objects/${schema?.kind}/${element.id}`);

  return (
    <Link
      to={url}
      tabIndex={-1}
      className="flex items-center gap-2 overflow-hidden"
      data-testid="ipam-tree-item">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span className="truncate">{element.name}</span>
    </Link>
  );
};

export default HierarchicalTree;
