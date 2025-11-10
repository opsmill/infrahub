import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect, useState } from "react";
import type { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { Link, useNavigate, useParams } from "react-router";

import { useLazyQuery } from "@/shared/api/graphql/useQuery";
import { Badge } from "@/shared/components/ui/badge";
import { SearchInput, type SearchInputProps } from "@/shared/components/ui/search-input";
import { Tree, type TreeItemProps } from "@/shared/components/ui/tree";
import { debounce } from "@/shared/utils/common";

import { TREE_ROOT_ID } from "@/entities/ipam/constants";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { GET_PREFIXES_ONLY } from "@/entities/ipam/ipam-tree/api/prefixes";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import { genericSchemasAtom, nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

import { ipamTreeAtom, reloadIpamTreeAtom } from "./ipam-tree.state";
import {
  EMPTY_TREE,
  formatIPPrefixResponseForTreeView,
  getTreeItemAncestors,
  type PrefixData,
  updateTreeData,
} from "./utils";

export default function IpamTree({ className }: { className?: string }) {
  const { objectId: prefix } = useParams();
  const { currentIpNamespace } = useCurrentIpNamespace();
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [treeData, setTreeData] = useAtom(ipamTreeAtom);
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);
  const [fetchPrefixes] = useLazyQuery<
    PrefixData,
    { parentIds?: string[]; search?: string; ipNamespaceIds: string[] }
  >(GET_PREFIXES_ONLY);
  const navigate = useNavigate();

  useEffect(() => {
    setLoading(true);
    reloadIpamTree(prefix).then((newTree) => {
      if (prefix) {
        const ancestorIds = getTreeItemAncestors(newTree, prefix).map(({ id }) => id);
        setExpandedIds(ancestorIds);
      }
      setLoading(false);
    });
  }, [currentIpNamespace.id]);

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (element.children.length > 0) return; // To avoid refetching data

    const { data } = await fetchPrefixes({
      variables: { parentIds: [element.id.toString()], ipNamespaceIds: [currentIpNamespace.id] },
    });

    if (!data) return;

    const treeNodes = formatIPPrefixResponseForTreeView(data);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  const handleSearch: SearchInputProps["onChange"] = async (e) => {
    const value = e.target.value as string;

    if (value === "") {
      return reloadIpamTree(prefix).then((newTree) => {
        if (prefix) {
          const ancestorIds = getTreeItemAncestors(newTree, prefix).map(({ id }) => id);
          setExpandedIds(ancestorIds);
        }
        setLoading(false);
      });
    }

    const { data } = await fetchPrefixes({
      variables: { search: value, ipNamespaceIds: [currentIpNamespace.id] },
    });

    if (!data) return;

    const treeNodes = formatIPPrefixResponseForTreeView(data).map((element) => ({
      ...element,
      isBranch: false,
      parent: TREE_ROOT_ID,
    }));

    setTreeData(updateTreeData(EMPTY_TREE, TREE_ROOT_ID, treeNodes));
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

  return (
    <>
      <SearchInput
        containerClassName="p-1"
        className="border-transparent"
        placeholder="Filter..."
        onChange={debouncedHandleSearch}
      />

      <Tree
        loading={isLoading}
        data={treeData}
        itemContent={IpamTreeItem}
        onLoadData={onLoadData}
        selectedIds={prefix ? [prefix] : []}
        defaultExpandedIds={expandedIds}
        onNodeSelect={({ element, isSelected }) => {
          if (!isSelected) return;

          const url = getObjectDetailsUrl(element.metadata?.kind as string, element.id.toString());
          navigate(url);
        }}
        className={className}
        data-testid="ipam-tree"
      />
    </>
  );
}

const IpamTreeItem = ({ element }: TreeItemProps) => {
  const nodes = useAtomValue(nodeSchemasAtom);
  const generics = useAtomValue(genericSchemasAtom);

  const schema = [...nodes, ...generics].find(({ kind }) => kind === element.metadata?.kind);
  const url = getObjectDetailsUrl(element.metadata?.kind as string, element.id.toString());

  return (
    <Link
      to={url}
      tabIndex={-1}
      className="flex w-full items-center gap-2"
      data-testid="ipam-tree-item"
    >
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span>{element.name}</span>
      {!!element.metadata?.descendantsCount && (
        <Badge className="ml-auto">{element.metadata?.descendantsCount}</Badge>
      )}
    </Link>
  );
};
