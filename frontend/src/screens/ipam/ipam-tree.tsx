import { TreeItemProps, Tree, TreeProps } from "../../components/ui/tree";
import { useLazyQuery } from "../../hooks/useQuery";
import React, { useEffect, useState } from "react";
import { ITreeViewOnLoadDataProps } from "react-accessible-treeview";
import { Link, useNavigate } from "react-router-dom";
import { constructPath } from "../../utils/fetch";
import { Icon } from "@iconify-icon/react";
import { GET_PREFIXES_ONLY } from "../../graphql/queries/ipam/prefixes";
import { useAtomValue } from "jotai/index";
import { genericsState, IModelSchema, schemaState } from "../../state/atoms/schema.atom";
import { Skeleton } from "../../components/skeleton";

type PrefixNode = {
  id: string;
  display_label: string;
  parent: {
    node: {
      id: string;
      display_label: string;
    } | null;
  };
  children: {
    count: number;
  };
  __typename: string;
};

type PrefixData = {
  IpamIPPrefix: {
    edges: Array<{ node: PrefixNode }>;
  };
};

const ROOT_NODE_ID = "root" as const;

const formatIPPrefixResponseForTreeView = (data: PrefixData): TreeItemProps["element"][] => {
  const prefixes = data.IpamIPPrefix.edges.map(({ node }) => ({
    id: node.id,
    name: node.display_label,
    parent: node.parent.node?.id ?? ROOT_NODE_ID,
    children: [],
    isBranch: node.children.count > 0,
    metadata: {
      kind: node.__typename,
    },
  }));

  return prefixes;
};

const updateTreeData = (list: TreeProps["data"], id: string, children: TreeProps["data"]) => {
  const data = list.map((node) => {
    if (node.id === id) {
      node.children = children.map((el) => {
        return el.id;
      });
    }
    return node;
  });
  return [...data, ...children];
};

export default function IpamTree({ prefixSchema }: { prefixSchema?: IModelSchema }) {
  const [treeData, setTreeData] = useState<TreeProps["data"]>([
    {
      id: ROOT_NODE_ID,
      name: "",
      parent: null,
      children: [],
      isBranch: true,
    },
  ]);
  const [fetchPrefixes] = useLazyQuery<PrefixData, { parentIds: string[] }>(GET_PREFIXES_ONLY);
  const navigate = useNavigate();

  useEffect(() => {
    fetchPrefixes().then(({ data }) => {
      if (!data) return;

      const treeNodes = formatIPPrefixResponseForTreeView(data);

      const rootTreeNodes = treeNodes.filter(({ parent }) => parent === ROOT_NODE_ID);

      // assign all prefixes and IP addresses without parent to the root node
      setTreeData((tree) => updateTreeData(tree, ROOT_NODE_ID, rootTreeNodes));
    });
  }, []);

  const isLoading = !prefixSchema || treeData.length === 1;

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (element.children.length > 0) return; // To avoid refetching data

    const { data } = await fetchPrefixes({
      variables: { parentIds: [element.id.toString()] },
    });

    if (!data) return;

    const treeNodes = formatIPPrefixResponseForTreeView(data);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  return (
    <nav className="min-w-64">
      <h3 className="font-semibold mb-2">Navigation</h3>

      {isLoading ? (
        <IpamTreeLoader />
      ) : (
        <Tree
          data={treeData}
          itemContent={IpamTreeItem}
          onLoadData={onLoadData}
          onNodeSelect={({ element, isSelected }) => {
            if (!isSelected) return;

            const url = constructPath(`/ipam/prefixes/${encodeURIComponent(element.name)}`);
            navigate(url);
          }}
        />
      )}
    </nav>
  );
}

const IpamTreeItem = ({ element }: TreeItemProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const schema = [...nodes, ...generics].find(({ kind }) => kind === element.metadata?.kind);
  const url = constructPath(`/ipam/prefixes/${encodeURIComponent(element.name)}`);

  return (
    <Link to={url} tabIndex={-1} className="flex items-center gap-2 overflow-hidden">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span className="truncate">{element.name}</span>
    </Link>
  );
};

const IpamTreeLoader = () => {
  return (
    <div className="space-y-2 border rounded p-1.5">
      <Skeleton className="h-4 w-11/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-4/5" />
      <Skeleton className="h-4 w-10/12" />
      <Skeleton className="h-4 w-9/12" />
      <Skeleton className="h-4 w-11/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-8/12" />
      <Skeleton className="h-4 w-10/12" />
    </div>
  );
};
