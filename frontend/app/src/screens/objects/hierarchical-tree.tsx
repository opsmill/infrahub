import { Tree, TreeItemProps, TreeProps } from "@/components/ui/tree";
import {
  objectAncestorsQuery,
  objectChildrenQuery,
  objectTopLevelTreeQuery,
} from "@/graphql/queries/objects/objectTreeQuery";
import { useLazyQuery } from "@/hooks/useQuery";
import { TREE_ROOT_ID } from "@/screens/ipam/constants";
import { EMPTY_TREE, PrefixNode, updateTreeData } from "@/screens/ipam/ipam-tree/utils";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IModelSchema, genericsState, schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { constructPath } from "@/utils/fetch";
import { getObjectDetailsUrl } from "@/utils/objects";
import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { Link, useNavigate } from "react-router-dom";

export type HierarchicalTreeProps = {
  schema: IModelSchema;
  className?: string;
  currentNodeId?: string;
};

export const HierarchicalTree = ({ schema, currentNodeId, className }: HierarchicalTreeProps) => {
  const navigate = useNavigate();
  const currentBranch = useAtomValue(currentBranchAtom);
  const currentDate = useAtomValue(datetimeAtom);

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
    setExpandedIds(
      orderedAncestorsFormattedForTree.map((x) => x.id).filter((id) => id !== currentNodeId)
    );
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
  }, [schema.kind, currentBranch, currentDate]);

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (!element.isBranch || element.children.length > 0) return; // To avoid refetching data

    const { data } = await getTreeItemChildren({
      variables: { parentIds: [element.id.toString()] },
    });

    if (!data) return;

    const treeNodes = formatResponseDataForTreeView(data[schema.kind!]);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  return (
    <Tree
      loading={isLoading}
      data={treeData}
      itemContent={ObjectTreeItem}
      defaultExpandedIds={expandedIds}
      selectedIds={selectedIds}
      onLoadData={onLoadData}
      onNodeSelect={({ element, isSelected }) => {
        if (!isSelected) return;

        const url = constructPath(
          getObjectDetailsUrl(element.id.toString(), element.metadata?.kind as string)
        );
        navigate(url);
      }}
      className={className}
      data-testid="hierarchical-tree"
    />
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
      data-testid="hierarchical-tree-item"
    >
      {schema?.icon ? (
        <Icon icon={schema.icon as string} className="w-4" />
      ) : (
        <div className="w-4" />
      )}
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
