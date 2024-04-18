import { TreeItemProps, Tree, TreeProps } from "../../components/ui/tree";
import { useLazyQuery } from "../../hooks/useQuery";
import { gql } from "@apollo/client";
import React, { useEffect, useState } from "react";
import { Spinner } from "../../components/ui/spinner";
import { ITreeViewOnLoadDataProps } from "react-accessible-treeview";
import { Link, useNavigate } from "react-router-dom";
import { constructPath } from "../../utils/fetch";
import { Icon } from "@iconify-icon/react";

const GET_PREFIXES = gql`
  query GET_PREFIXES($parentIds: [ID!]) {
    IpamIPPrefix(parent__ids: $parentIds) {
      edges {
        node {
          id
          display_label
          parent {
            node {
              id
            }
          }
          children {
            count
          }
          ip_addresses {
            count
          }
        }
      }
    }
  }
`;

type PrefixNode = {
  id: string;
  display_label: string;
  parent: string | null;
  children: string[];
  isBranch: boolean;
  icon: string | null;
  count: number;
  ipCount?: number;
};

type PrefixEdge = {
  node: PrefixNode & {
    parent: {
      node: {
        id: string;
        display_label: string;
      } | null;
    };
    utilization: {
      value: number;
    };
    children: {
      count: number;
    };
    descendants: {
      count: number;
    };
    ip_addresses: {
      count: number;
    };
  };
};

type PrefixData = {
  IpamIPPrefix: {
    edges: PrefixEdge[];
  };
};

const toTreeNodeFormat = (data: PrefixData): TreeItemProps["element"][] => {
  const prefixes = data.IpamIPPrefix.edges.map(({ node }) => ({
    id: node.id,
    name: node.display_label,
    parent: node.parent.node?.id ?? "root",
    children: [],
    isBranch: node.children.count > 0 || node.ip_addresses.count > 0,
    metadata: {
      category: "IP_PREFIX",
      icon: "mdi:ip-network",
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

export default function IpamTree() {
  const [treeData, setTreeData] = useState<TreeProps["data"]>([
    {
      id: "root",
      name: "",
      parent: null,
      children: [],
      isBranch: true,
    },
  ]);
  const [fetchPrefixes] = useLazyQuery<PrefixData, { parentIds: string[] }>(GET_PREFIXES);
  const navigate = useNavigate();

  useEffect(() => {
    fetchPrefixes().then(({ data }) => {
      if (!data) return;

      const treeNodes = toTreeNodeFormat(data);

      const rootTreeNodes = treeNodes.filter(({ parent }) => parent === "root");

      // assign all prefixes and IP addresses without parent to the root node
      setTreeData((tree) => updateTreeData(tree, "root", rootTreeNodes));
    });
  }, []);

  if (treeData.length === 1) return <Spinner />;

  const onLoadData = async ({ element }: ITreeViewOnLoadDataProps) => {
    if (element.children.length > 0) return;

    const { data } = await fetchPrefixes({
      variables: { parentIds: [element.id.toString()] },
    });

    if (!data) return;

    const treeNodes = toTreeNodeFormat(data);
    setTreeData((tree) => updateTreeData(tree, element.id.toString(), treeNodes));
  };

  return (
    <nav className="min-w-64">
      <h3 className="font-semibold mb-2">Navigation</h3>

      <Tree
        data={treeData}
        itemContent={IpamTreeItem}
        onLoadData={onLoadData}
        onNodeSelect={({ element, isSelected }) => {
          if (!isSelected) return;

          const url = constructPath(
            element.metadata?.category === "IP_PREFIX"
              ? `/ipam/prefixes/${encodeURIComponent(element.name)}`
              : `/ipam/ip_address/${encodeURIComponent(element.name)}`
          );
          navigate(url);
        }}
      />
    </nav>
  );
}

const IpamTreeItem = ({ element }: TreeItemProps) => {
  const url = element.metadata
    ? constructPath(
        element.metadata.category === "IP_PREFIX"
          ? `/ipam/prefixes/${encodeURIComponent(element.name)}`
          : `/ipam/ip_address/${encodeURIComponent(element.name)}`
      )
    : "";

  return (
    <Link to={url} tabIndex={-1} className="flex items-center gap-2">
      {element.metadata?.icon ? (
        <Icon icon={element.metadata.icon as string} />
      ) : (
        <div className="w-4" />
      )}
      {element.name}
    </Link>
  );
};
