import { useAtomValue } from "jotai";
import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
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
import { IPAM_TREE_ROOT_ID } from "@/screens/ipam/constants";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "@/utils/fetch";
import { NodeId } from "react-accessible-treeview";
import { getObjectDetailsUrl } from "@/utils/objects";
import { objectTreeQuery } from "@/graphql/queries/objects/objectTreeQuery";
import { currentBranchAtom } from "@/state/atoms/branches.atom";

export type HierarchicalTreeProps = {
  schema: IModelSchema;
  className?: string;
  currentNodeId?: string;
};

export const HierarchicalTree = ({ schema, currentNodeId, className }: HierarchicalTreeProps) => {
  const navigate = useNavigate();
  const branch = useAtomValue(currentBranchAtom);

  const [treeData, setTreeData] = useState<TreeProps["data"]>(EMPTY_IPAM_TREE);
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);

  const query = gql(objectTreeQuery({ kind: schema.kind, id: currentNodeId }));
  const [getObjectTree] = useLazyQuery(query);
  const [isLoading, setLoading] = useState(true);

  const fetchTree = async () => {
    setLoading(true);

    const { data } = await getObjectTree();

    let rootNodeIds: string[] = [];
    const objectTreeData = data[schema.kind as string].edges;
    const tree = objectTreeData.map(({ node }: { node: any }) => {
      const nodeId = node?.id;
      const parentId = node.parent?.node?.id ?? IPAM_TREE_ROOT_ID;

      if (parentId === IPAM_TREE_ROOT_ID) rootNodeIds.push(nodeId);

      return {
        id: node.id,
        name: node.display_label,
        children: objectTreeData
          .filter((object: any) => object.node?.parent?.node?.id === nodeId)
          .map((object: any) => object.node?.id),
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
  };

  useEffect(() => {
    fetchTree();
  }, [schema.kind, currentNodeId, branch]);

  return (
    <Card className={className}>
      <Tree
        loading={isLoading}
        data={treeData}
        itemContent={ObjectTreeItem}
        defaultExpandedIds={expandedIds}
        selectedIds={currentNodeId ? [currentNodeId] : undefined}
        onNodeSelect={({ element, isSelected, isBranch }) => {
          if (!isSelected || isBranch) return;

          const url = getObjectDetailsUrl(element.id.toString(), element.metadata?.kind as string);
          navigate(url);
        }}
        data-testid="hierarchical-tree"
      />
    </Card>
  );
};

const ObjectTreeItem = ({ element }: TreeItemProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const schema = [...nodes, ...generics].find(({ kind }) => kind === element.metadata?.kind);

  const url = constructPath(getObjectDetailsUrl(element.id.toString(), schema?.kind as string));
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
