import { Icon } from "@iconify-icon/react";
import { type TreeProps as AriaTreeProps, Collection } from "react-aria-components";
import { useLocation } from "react-router";

import { Tree, TreeItem, TreeItemContent } from "@/shared/components/aria/tree";

import type { DiffNode } from "@/entities/diff/ui/node-diff/types";
import { DiffBadge } from "@/entities/diff/ui/node-diff/utils";
import { buildDiffTreeItems, type DiffTreeItem } from "@/entities/diff/utils/build-diff-tree-items";

interface DiffTreeProps extends Omit<AriaTreeProps<DiffTreeItem>, "items" | "children"> {
  nodes: Array<DiffNode>;
}

export default function DiffTree({ nodes, ...props }: DiffTreeProps) {
  const location = useLocation();
  const diffTreeItems = buildDiffTreeItems(nodes);
  const selectedDiffNodeId = location.hash?.slice(1) || null;

  return (
    <Tree
      aria-label="diff tree"
      items={diffTreeItems}
      defaultExpandedKeys={diffTreeItems.map((n) => n.id)}
      {...props}
    >
      {function renderTreeItem(item) {
        return (
          <TreeItem
            textValue={item.label}
            {...(item.isNode
              ? {
                  href: { ...location, hash: `#${item.id}` },
                  routerOptions: { replace: true },
                  className: selectedDiffNodeId === item.id ? "bg-gray-100" : undefined,
                }
              : {})}
          >
            <TreeItemContent>
              {item.isNode ? (
                <DiffBadge
                  status={item.status}
                  hasConflicts={item.hasConflicts}
                  size="icon"
                  className="mr-2"
                />
              ) : (
                <Icon icon={item.icon} className="mr-2" />
              )}

              <span className="truncate">{item.label}</span>
            </TreeItemContent>

            <Collection items={item.children}>{renderTreeItem}</Collection>
          </TreeItem>
        );
      }}
    </Tree>
  );
}
