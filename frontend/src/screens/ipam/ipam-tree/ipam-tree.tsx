import { TreeItemProps, Tree } from "../../../components/ui/tree";
import { useLazyQuery } from "../../../hooks/useQuery";
import React, { useEffect, useState } from "react";
import { ITreeViewOnLoadDataProps, NodeId } from "react-accessible-treeview";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "@iconify-icon/react";
import * as R from "ramda";

import {
  GET_PREFIX_ANCESTORS,
  GET_PREFIXES_ONLY,
  GET_TOP_LEVEL_PREFIXES,
} from "../../../graphql/queries/ipam/prefixes";
import { useAtomValue } from "jotai/index";
import { genericsState, schemaState } from "../../../state/atoms/schema.atom";
import { constructPathForIpam } from "../common/utils";
import { IpamTreeSkeleton } from "./ipam-tree-skeleton";
import { IP_PREFIX_GENERIC, IPAM_ROUTE, IPAM_TREE_ROOT_ID } from "../constants";
import {
  formatIPPrefixResponseForTreeView,
  PrefixData,
  ROOT_TREE_ITEM,
  updateTreeData,
} from "./utils";

export default function IpamTree() {
  const { prefix } = useParams();
  const [selected, setSelected] = useState<NodeId[]>([]);
  const [isLoading, setLoading] = useState(true);
  const [treeData, setTreeData] = useState([ROOT_TREE_ITEM]);
  const [fetchTopLevelIpPrefixes] = useLazyQuery<PrefixData>(GET_TOP_LEVEL_PREFIXES);
  const [fetchPrefixAncestors] = useLazyQuery<PrefixData>(GET_PREFIX_ANCESTORS);
  const [fetchPrefixes] = useLazyQuery<PrefixData, { parentIds: string[] }>(GET_PREFIXES_ONLY);
  const navigate = useNavigate();

  useEffect(() => {
    fetchTopLevelIpPrefixes()
      .then(({ data }) => {
        if (!data) return;

        const topLevelTreeItems = formatIPPrefixResponseForTreeView(data);

        // assign all prefixes and IP addresses without parent to the root node
        return updateTreeData(treeData, IPAM_TREE_ROOT_ID, topLevelTreeItems);
      })
      .then((tree) => {
        if (!tree) return;

        if (!prefix) {
          setTreeData(tree);
          setLoading(false);
          return;
        }

        fetchPrefixAncestors({ variables: { ip: prefix } })
          .then(({ data }) => {
            if (!data) return;

            const ancestors = data[IP_PREFIX_GENERIC].edges.map(({ node }) => ({
              id: node.id,
              parentId: node.parent.node?.id ?? IPAM_TREE_ROOT_ID,
            }));

            const parentToChildMap: Record<string, string> = {};

            ancestors.forEach(({ id, parentId }) => {
              parentToChildMap[parentId] = id;
            });

            const orderedAncestorIds: string[] = [];

            const traverseHierarchy = (map: Record<string, string>, parentId: string) => {
              const childId = map[parentId];
              if (!childId) return;

              orderedAncestorIds.push(childId);
              traverseHierarchy(map, childId);
            };

            traverseHierarchy(parentToChildMap, IPAM_TREE_ROOT_ID);

            return orderedAncestorIds;
          })
          .then((orderedAncestorIds) => {
            if (!orderedAncestorIds) return;

            fetchPrefixes({ variables: { parentIds: orderedAncestorIds } }).then(({ data }) => {
              if (!data) return;

              const treeItems = formatIPPrefixResponseForTreeView(data);
              const groupedByParent = R.groupBy(
                (node) => node.parent?.toString() ?? IPAM_TREE_ROOT_ID,
                treeItems
              );

              const newTree = orderedAncestorIds.reduce((acc, currentAncestorId) => {
                const children = groupedByParent[currentAncestorId];
                if (!children) return acc;
                return updateTreeData(acc, currentAncestorId, children);
              }, tree);

              const currentPrefix = newTree.find(({ name }) => name === prefix);
              setTreeData(newTree);
              setSelected(
                currentPrefix ? [...orderedAncestorIds, currentPrefix.id] : orderedAncestorIds
              );
              setLoading(false);
            });
          });
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
          defaultSelectedIds={selected}
          defaultExpandedIds={selected}
          onNodeSelect={({ element, isSelected }) => {
            if (!isSelected) return;

            const url = constructPathForIpam(
              `${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(element.name)}`
            );
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
  const url = constructPathForIpam(`${IPAM_ROUTE.PREFIXES}/${encodeURIComponent(element.name)}`);

  return (
    <Link to={url} tabIndex={-1} className="flex items-center gap-2 overflow-hidden">
      {schema?.icon ? <Icon icon={schema.icon as string} /> : <div className="w-4" />}
      <span className="truncate">{element.name}</span>
    </Link>
  );
};
