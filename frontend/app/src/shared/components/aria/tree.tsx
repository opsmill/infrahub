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
  Button,
} from "react-aria-components";

import { Row } from "@/shared/components/container";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

export const Tree = AriaTree;

export interface TreeItemProps extends AriaTreeItemProps {}
export const TreeItem = ({ className, ...props }: TreeItemProps) => {
  return (
    <AriaTreeItem
      className={classNames(
        focusVisibleStyle,
        "cursor-pointer rounded-md border border-transparent text-sm mix-blend-multiply hover:bg-neutral-100",
        className
      )}
      {...props}
    />
  );
};

export interface TreeItemContentProps extends AriaTreeItemContentProps {
  onExpandedChange?: () => void;
}
export const TreeItemContent = ({ onExpandedChange, children, ...props }: TreeItemContentProps) => {
  return (
    <AriaTreeItemContent {...props}>
      {(contentProps) => {
        const { hasChildItems, isExpanded, level } = contentProps;
        return (
          <Row className="gap-0" style={{ paddingLeft: (level - 1) * 23 }}>
            {hasChildItems ? (
              <Button
                slot="chevron"
                onPress={onExpandedChange}
                className={classNames(
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
          </Row>
        );
      }}
    </AriaTreeItemContent>
  );
};

export function TreeItemLoader(props: AriaTreeLoadMoreItemProps) {
  return (
    <AriaTreeLoadMoreItem {...props}>
      {({ level }) => (
        <LoadingIndicator
          className="h-8 justify-start text-sm"
          style={{ paddingLeft: level * 32 }}
        />
      )}
    </AriaTreeLoadMoreItem>
  );
}

const DotIcon = (props: React.HTMLAttributes<SVGSVGElement>) => (
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
