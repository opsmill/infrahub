import { useAtom, useAtomValue, useSetAtom } from "jotai";
import React, { useEffect, useState } from "react";
import { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import { TreeItemProps, Tree } from "../../../components/ui/tree";
import { useLazyQuery } from "../../../hooks/useQuery";

import { GET_PREFIXES_ONLY } from "../../../graphql/queries/ipam/prefixes";
import { genericsState, schemaState } from "../../../state/atoms/schema.atom";
import { constructPathForIpam } from "../common/utils";
import { IpamTreeSkeleton } from "./ipam-tree-skeleton";
import { IPAM_ROUTE } from "../constants";
import {
  formatIPPrefixResponseForTreeView,
  getTreeItemAncestors,
  PrefixData,
  updateTreeData,
} from "./utils";
import { ipamTreeAtom, reloadIpamTreeAtom } from "./ipam-tree.state";

export default function IpamTree() {
  const { prefix } = useParams();
  const [expandedIds, setExpandedIds] = useState<NodeId[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [treeData, setTreeData] = useAtom(ipamTreeAtom);
  const reloadIpamTree = useSetAtom(reloadIpamTreeAtom);
  const [fetchPrefixes] = useLazyQuery<PrefixData, { parentIds: string[] }>(GET_PREFIXES_ONLY);
  const navigate = useNavigate();

  useEffect(() => {
    reloadIpamTree(prefix).then((newTree) => {
      if (prefix) {
        const ancestorIds = getTreeItemAncestors(newTree, prefix).map(({ id }) => id);
        setExpandedIds(ancestorIds);
      }
      setLoading(false);
    });
  }, []);

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
      <h3 className="font-semibold text-sm px-1 pt-1.5 pb-4">Navigation</h3>

      {isLoading ? (
        <IpamTreeSkeleton />
      ) : (
        <Tree
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
          data-testid="ipam-tree"
        />
      )}
    </nav>
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
      className="flex items-center gap-2 overflow-hidden"
      data-testid="ipam-tree-item">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span className="truncate">{element.name}</span>
    </Link>
  );
};
