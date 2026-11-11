import { ChevronRightIcon } from "lucide-react";
import type React from "react";
import {
  Tree as AriaTree,
  TreeItem as AriaTreeItem,
  TreeItemContent as AriaTreeItemContent,
  type TreeItemContentProps as AriaTreeItemContentProps,
  type TreeItemProps as AriaTreeItemProps,
  TreeLoadMoreItem as AriaTreeLoadMoreItem,
  type TreeLoadMoreItemProps as AriaTreeLoadMoreItemProps,
  type TreeProps as AriaTreeProps,
  Button,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Spinner } from "../spinner/spinner";

const ITEM_INDENT_PX = 23;
const LOADER_INDENT_PX = 32;

function DotIcon(props: React.HTMLAttributes<SVGSVGElement>) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width="26"
      height="6"
      viewBox="0 0 6 6"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      <path
        fillRule="evenodd"
        clipRule="evenodd"
        d="M2.9999 4.3C3.71787 4.3 4.2999 3.71797 4.2999 3C4.2999 2.28203 3.71787 1.7 2.9999 1.7C2.28193 1.7 1.6999 2.28203 1.6999 3C1.6999 3.71797 2.28193 4.3 2.9999 4.3ZM2.9999 5.1C4.1597 5.1 5.0999 4.1598 5.0999 3C5.0999 1.8402 4.1597 0.900002 2.9999 0.900002C1.8401 0.900002 0.899902 1.8402 0.899902 3C0.899902 4.1598 1.8401 5.1 2.9999 5.1Z"
      />
    </svg>
  );
}

export type TreeProps<T> = AriaTreeProps<T>;
export const Tree = AriaTree;

export interface TreeItemProps extends AriaTreeItemProps {}

export function TreeItem({ className, ...props }: TreeItemProps) {
  return (
    <AriaTreeItem
      className={composeAriaClassName(
        className,
        cn(
          focusVisibleStyle,
          "cursor-pointer rounded-md border border-transparent text-sm text-subtle hover:bg-highlight hover:text-highlight-foreground"
        )
      )}
      {...props}
    />
  );
}

export interface TreeItemContentProps extends AriaTreeItemContentProps {
  onExpandedChange?: () => void;
}

export function TreeItemContent({ onExpandedChange, children, ...props }: TreeItemContentProps) {
  return (
    <AriaTreeItemContent {...props}>
      {(contentProps) => {
        const { hasChildItems, isExpanded, level } = contentProps;
        return (
          <div
            className="flex items-center gap-0"
            style={{ paddingLeft: (level - 1) * ITEM_INDENT_PX }}
          >
            {hasChildItems ? (
              <Button
                slot="chevron"
                onPress={onExpandedChange}
                className={cn(
                  "inline-flex size-8 shrink-0 items-center justify-center duration-200",
                  isExpanded && "rotate-90"
                )}
              >
                <ChevronRightIcon className="size-4" />
              </Button>
            ) : (
              <div className="inline-flex size-8 shrink-0 items-center justify-center">
                <DotIcon />
              </div>
            )}

            {typeof children === "function" ? children(contentProps) : children}
          </div>
        );
      }}
    </AriaTreeItemContent>
  );
}

export function TreeItemLoader(props: AriaTreeLoadMoreItemProps) {
  return (
    <AriaTreeLoadMoreItem {...props}>
      {({ level }) => (
        <div
          className="flex h-8 items-center justify-start gap-2 text-sm text-subtle-muted"
          style={{ paddingLeft: level * LOADER_INDENT_PX }}
        >
          <Spinner />
          <span>Loading...</span>
        </div>
      )}
    </AriaTreeLoadMoreItem>
  );
}
