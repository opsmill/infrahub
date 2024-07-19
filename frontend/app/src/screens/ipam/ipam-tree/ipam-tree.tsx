import { Tree, TreeItemProps } from "@/components/ui/tree";
import { useLazyQuery } from "@/hooks/useQuery";
import { Icon } from "@iconify-icon/react";
import { useAtom, useAtomValue, useSetAtom } from "jotai";
import { useEffect, useState } from "react";
import { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { Link, useNavigate, useParams } from "react-router-dom";

import { GET_PREFIXES_ONLY } from "@/graphql/queries/ipam/prefixes";
import { defaultIpNamespaceAtom } from "@/screens/ipam/common/namespace.state";
import { constructPathForIpam } from "@/screens/ipam/common/utils";
import { IPAM_QSP, IPAM_ROUTE } from "@/screens/ipam/constants";
import { genericsState, schemaState } from "@/state/atoms/schema.atom";
import { StringParam, useQueryParam } from "use-query-params";
import { ipamTreeAtom, reloadIpamTreeAtom } from "./ipam-tree.state";
import {
  PrefixData,
  formatIPPrefixResponseForTreeView,
  getTreeItemAncestors,
  updateTreeData,
} from "./utils";
import { Badge } from "@/components/ui/badge";
import { SearchInput, SearchInputProps } from "@/components/ui/search-input";
import { debounce } from "@/utils/common";

export default function IpamTree({ className }: { className?: string }) {
  const { prefix } = useParams();
  const [namespace] = useQueryParam(IPAM_QSP.NAMESPACE, StringParam);
  const defaultIpNamespace = useAtomValue(defaultIpNamespaceAtom);
  const [treeData, setTreeData] = useAtom(ipamTreeAtom);
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [fetchPrefixes] = useLazyQuery<PrefixData, { parentIds?: string[]; search?: string }>(
    GET_PREFIXES_ONLY
  );
  const navigate = useNavigate();

  useEffect(() => {
    const currentIpNamespace = namespace ?? defaultIpNamespace;
    if (!currentIpNamespace) return;

    reloadIpamTree(currentIpNamespace, prefix).then((newTree) => {
      if (prefix) {
        const ancestorIds = getTreeItemAncestors(newTree, prefix).map(({ id }) => id);
        setExpandedIds(ancestorIds);
      }
      setLoading(false);
    });
  }, [namespace, defaultIpNamespace]);

  const handleNodeSelect = ({ element, isSelected }) => {
    if (!isSelected) return;

    const url = constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${element.id}`);

    navigate(url);
  };

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (element.children.length > 0) return; // To avoid refetching data

    const { data } = await fetchPrefixes({
      variables: { parentIds: [element.id.toString()] },
    });

    if (!data) return;

    const treeNodes = formatIPPrefixResponseForTreeView(data);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  const handleSearch: SearchInputProps["onChange"] = async (e) => {
    const value = e.target.value as string;

    const { data } = await fetchPrefixes({
      variables: { search: value },
    });

    if (!data) return;

    const treeNodes = formatIPPrefixResponseForTreeView(data);
    console.log("treeNodes: ", treeNodes);
  };

  const debouncedHandleSearch = debounce(handleSearch, 500);

  return (
    <Tree
      loading={isLoading}
      data={treeData}
      itemContent={IpamTreeItem}
      onLoadData={onLoadData}
      selectedIds={prefix ? [prefix] : []}
      defaultExpandedIds={expandedIds}
      onNodeSelect={({ element, isSelected }) => {
        if (!isSelected) return;

        const url = constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${element.id}`);
        navigate(url);
      }}
      className={className}
      data-testid="ipam-tree"
    />
  );
}

const IpamTreeItem = ({ element }: TreeItemProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);

  const schema = [...nodes, ...generics].find(({ kind }) => kind === element.metadata?.kind);
  const url = constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${element.id}`);

  return (
    <Link
      to={url}
      tabIndex={-1}
      className="flex items-center gap-2 w-full"
      data-testid="ipam-tree-item">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span>{element.name}</span>
      {!!element.metadata?.descendantsCount && (
        <Badge className="ml-auto">{element.metadata?.descendantsCount}</Badge>
      )}
    </Link>
  );
};
