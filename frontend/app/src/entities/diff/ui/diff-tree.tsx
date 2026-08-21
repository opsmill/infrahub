import { Tree, TreeItem, TreeItemContent, type TreeProps } from "@infrahub/ui";
import { Collection } from "react-aria-components";
import { useLocation } from "react-router";

import { Icon } from "@/shared/components/display/icon";

import { buildDiffTreeItems, type DiffTreeItem } from "@/entities/diff/ui/build-diff-tree-items";
import type { DiffNode } from "@/entities/diff/ui/node-diff/types";
import { DiffBadge } from "@/entities/diff/ui/node-diff/utils";

interface DiffTreeProps extends Omit<TreeProps<DiffTreeItem>, "items" | "children"> {
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
                  className:
                    selectedDiffNodeId === item.id
                      ? "bg-selected text-selected-foreground shadow-selected hover:bg-selected-highlight"
                      : undefined,
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
