import { TreeItemProps, TreeProps } from "../../../components/ui/tree";
import { IPAM_TREE_ROOT_ID } from "../constants";
import { IPAM_PREFIX_GENERIC } from "../../../config/constants";

export type PrefixNode = {
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

export type PrefixData = {
  IpamIPPrefix: {
    edges: Array<{ node: PrefixNode }>;
  };
};

export const ROOT_TREE_ITEM: TreeItemProps["element"] = {
  id: IPAM_TREE_ROOT_ID,
  name: "",
  parent: null,
  children: [],
  isBranch: true,
};

export const formatIPPrefixResponseForTreeView = (data: PrefixData): TreeItemProps["element"][] => {
  const prefixes = (data[IPAM_PREFIX_GENERIC] || data.IpamIPPrefix).edges.map(({ node }) => ({
    id: node.id,
    name: node.display_label,
    parent: node.parent.node?.id ?? IPAM_TREE_ROOT_ID,
    children: [],
    isBranch: node.children.count > 0,
    metadata: {
      kind: node.__typename,
    },
  }));

  return prefixes;
};

export const updateTreeData = (
  list: TreeProps["data"],
  id: string,
  children: TreeProps["data"]
) => {
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
