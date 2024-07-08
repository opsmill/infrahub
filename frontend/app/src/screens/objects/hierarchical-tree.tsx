import { useAtomValue } from "jotai";
import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import { EMPTY_TREE, PrefixNode, updateTreeData } from "@/screens/ipam/ipam-tree/utils";
import { genericsState, IModelSchema, schemaState } from "@/state/atoms/schema.atom";
import { Card } from "@/components/ui/card";
import { useEffect, useState } from "react";
import { useLazyQuery } from "@/hooks/useQuery";
import { gql } from "@apollo/client";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";
import { Link, useNavigate } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { constructPath } from "@/utils/fetch";
import { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { getObjectDetailsUrl } from "@/utils/objects";
import {
  objectAncestorsQuery,
  objectChildrenQuery,
  objectTopLevelTreeQuery,
} from "@/graphql/queries/objects/objectTreeQuery";
import { currentBranchAtom } from "@/state/atoms/branches.atom";

export type HierarchicalTreeProps = {
  schema: IModelSchema;
  className?: string;
  currentNodeId?: string;
};

export const HierarchicalTree = ({ schema, currentNodeId, className }: HierarchicalTreeProps) => {
  const navigate = useNavigate();
  const branch = useAtomValue(currentBranchAtom);

  const [treeData, setTreeData] = useState<TreeProps["data"]>(EMPTY_TREE);
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);
  const [selectedIds, setSelectedIds] = useState<NodeId[]>([]);

  const [getObjectTopLevelTree] = useLazyQuery(gql(objectTopLevelTreeQuery({ kind: schema.kind })));
  const [getObjectAncestors] = useLazyQuery(gql(objectAncestorsQuery({ kind: schema.kind })));
  const [getTreeItemChildren] = useLazyQuery(gql(objectChildrenQuery({ kind: schema.kind })));
  const [isLoading, setLoading] = useState(true);

  const fetchTree = async () => {
    setLoading(true);
    const { data } = await getObjectTopLevelTree();
    if (!data) return;

    const topLevelTreeItems = formatResponseDataForTreeView(data[schema.kind!]);
    const treeWithTopLevelPrefixesOnly = updateTreeData(
      EMPTY_TREE,
      TREE_ROOT_ID,
      topLevelTreeItems
    );

    if (!currentNodeId) {
      return treeWithTopLevelPrefixesOnly;
    }

    const { data: objectAncestorsData } = await getObjectAncestors({
      variables: { ids: [currentNodeId] },
    });

    const currentObjectData = objectAncestorsData[schema.kind!].edges[0];

    if (!currentObjectData) {
      console.error(`Prefix ${currentNodeId} not found.`);
      return treeWithTopLevelPrefixesOnly;
    }

    const ancestors = currentObjectData.node.ancestors.edges;
    const orderedAncestors: typeof ancestors = [];

    const traverseHierarchy = (map: typeof ancestors, parentId: string | null) => {
      const child = map.find(({ node }: any) => {
        return node.parent.node === parentId || node.parent.node?.id === parentId;
      });
      if (!child) return;

      orderedAncestors.push(child);

      if (child?.node?.children?.count > 0) {
        child.node.children.edges.forEach((c: any) => orderedAncestors.push(c));
      }
      traverseHierarchy(map, child.node.id);
    };

    traverseHierarchy(ancestors, null);

    const orderedAncestorsFormattedForTree = formatResponseDataForTreeView({
      edges: [...orderedAncestors, currentObjectData],
    });
    setExpandedIds(orderedAncestorsFormattedForTree.map((x) => x.id));
    return updateHierarchicalTree(treeWithTopLevelPrefixesOnly, orderedAncestorsFormattedForTree);
  };

  useEffect(() => {
    setLoading(true);
    setSelectedIds([]);
    setExpandedIds([]);
    fetchTree().then((tree) => {
      if (!tree) return;

      setLoading(false);
      setTreeData(tree);
      if (currentNodeId) {
        setSelectedIds([currentNodeId]);
      }
    });
  }, [schema.kind, branch]);

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (element.children.length > 0) return; // To avoid refetching data

    const { data } = await getTreeItemChildren({
      variables: { parentIds: [element.id.toString()] },
    });

    if (!data) return;

    const treeNodes = formatResponseDataForTreeView(data[schema.kind!]);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  return (
    <Card className={className}>
      <Tree
        loading={isLoading}
        data={treeData}
        itemContent={ObjectTreeItem}
        defaultExpandedIds={expandedIds}
        selectedIds={selectedIds}
        onLoadData={onLoadData}
        onNodeSelect={({ element, isSelected }) => {
          if (!isSelected) return;

          const url = getObjectDetailsUrl(element.id.toString(), element.metadata?.kind as string);
          navigate(url);
        }}
        className="overflow-auto h-full"
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
      className="flex items-center gap-2"
      data-testid="hierarchical-tree-item">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span className="whitespace-nowrap">{element.name}</span>
    </Link>
  );
};

export const formatResponseDataForTreeView = (data: {
  edges: Array<{ node: PrefixNode }>;
}): TreeItemProps["element"][] => {
  return data.edges.map(({ node }) => ({
    id: node.id,
    name: node.display_label,
    parent: node.parent.node?.id ?? TREE_ROOT_ID,
    children: node.children?.edges?.map(({ node }) => node.id) ?? [],
    isBranch: node.children.count > 0,
    metadata: {
      kind: node.__typename,
    },
  }));
};

export const updateHierarchicalTree = (list: TreeProps["data"], children: TreeProps["data"]) => {
  return children.reduce((acc, currentChild) => {
    // new tree item needs to be added in 2 locations:
    // 1. new tree item should be ths in list (once only)
    // 2. new tree item's id should be in its parent's children array (once only)
    const data = acc.map((node) => {
      if (node.id === currentChild.parent) {
        node.children = [...new Set([...node.children, currentChild.id])];
      }
      return node;
    });

    const isChildrenAlreadyPresent = data.some(({ id }) => id === currentChild.id);

    return isChildrenAlreadyPresent ? data : [...data, currentChild];
  }, list);
};
