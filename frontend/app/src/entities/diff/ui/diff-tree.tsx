import { Icon } from "@iconify-icon/react";
import { TreeProps as AriaTreeProps, Collection } from "react-aria-components";
import { useLocation } from "react-router";

import { Tree, TreeItem, TreeItemContent } from "@/shared/components/aria/tree";

import { DiffNode } from "@/entities/diff/node-diff/types";
import { DiffBadge } from "@/entities/diff/node-diff/utils";
import { buildDiffTreeItems, DiffTreeItem } from "@/entities/diff/utils/build-diff-tree-items";

interface DiffTreeProps extends Omit<AriaTreeProps<DiffTreeItem>, "items" | "children"> {
  nodes: Array<DiffNode>;
}

export default function DiffTree({ nodes, ...props }: DiffTreeProps) {
  const location = useLocation();
  const diffTreeItems = buildDiffTreeItems(nodes);

  return (
    <Tree
      aria-label="diff tree"
      items={diffTreeItems}
      defaultExpandedKeys={diffTreeItems.map((n) => n.kind)}
      {...props}
    >
      {function renderTreeItem(item) {
        return (
          <TreeItem
            textValue={item.label}
            href={item.isNode ? { ...location, hash: `#${item.id}` } : undefined}
            routerOptions={{ replace: true }}
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
