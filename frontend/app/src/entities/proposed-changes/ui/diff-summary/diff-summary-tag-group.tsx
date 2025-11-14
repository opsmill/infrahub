import { Icon } from "@iconify-icon/react";
import { cva, type VariantProps } from "class-variance-authority";
import { CircleMinusIcon, CirclePlusIcon, RefreshCwIcon, TriangleAlertIcon } from "lucide-react";
import {
  Tag,
  TagGroup,
  type TagGroupProps,
  TagList,
  type TagListProps,
  type TagProps,
} from "react-aria-components";

import { disabledStyle, focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

export interface DiffSummaryProps<T>
  extends Omit<TagGroupProps, "children">,
    Pick<TagListProps<T>, "items" | "children" | "renderEmptyState"> {}

export function DiffSummaryTagGroup<T extends object>({
  items,
  children,
  renderEmptyState,
  ...props
}: DiffSummaryProps<T>) {
  return (
    <TagGroup aria-label="Diff summary" {...props}>
      <TagList className="inline-flex items-center gap-2 rounded-md bg-gray-100 p-1">
        <TagList items={items} renderEmptyState={renderEmptyState}>
          {children}
        </TagList>
      </TagList>
    </TagGroup>
  );
}

const diffSummaryTagStyles = cva(
  [
    disabledStyle,
    focusVisibleStyle,
    "relative inline-flex cursor-pointer items-center gap-1 rounded-full border border-transparent p-1 text-xs",
  ],
  {
    variants: {
      variant: {
        added: "",
        removed: "",
        updated: "",
        conflicts: "",
      },
      isMuted: {
        true: "opacity-50",
      },
    },
  }
);

export interface DiffSummaryTagProps extends VariantProps<typeof diffSummaryTagStyles>, TagProps {
  count: number;
  isClosable?: boolean;
}

export function DiffSummaryTag({
  count,
  variant,
  className,
  isClosable,
  isMuted,
  children,
  ...props
}: DiffSummaryTagProps) {
  return (
    <Tag
      className={classNames(diffSummaryTagStyles({ isMuted }), className)}
      textValue={`diff ${variant} count`}
      {...props}
    >
      <DiffSummaryIcon variant={variant} />
      {count}
      {isClosable && <DiffSummaryClose variant={variant} />}
    </Tag>
  );
}

export function DiffSummaryIcon({
  variant,
  ...props
}: Pick<VariantProps<typeof diffSummaryTagStyles>, "variant">) {
  const className = "size-3";

  switch (variant) {
    case "added":
      return <CirclePlusIcon className={className} {...props} />;
    case "removed":
      return <CircleMinusIcon className={className} {...props} />;
    case "updated":
      return <RefreshCwIcon className={className} {...props} />;
    case "conflicts":
      return <TriangleAlertIcon className={className} {...props} />;
    default:
      return null;
  }
}

const diffSummaryCloseStyles = cva(
  "-top-2 -right-2 absolute flex items-center justify-center rounded-full border-2 border-white",
  {
    variants: {
      variant: {
        added: "bg-green-200 text-green-800",
        removed: "bg-red-200 text-red-800",
        updated: "bg-blue-200 text-blue-800",
        conflicts: "bg-yellow-200 text-yellow-800",
      },
    },
  }
);

export interface DiffSummaryCloseProps
  extends React.HTMLProps<HTMLDivElement>,
    VariantProps<typeof diffSummaryCloseStyles> {}

export function DiffSummaryClose({ className, variant, ...props }: DiffSummaryCloseProps) {
  return (
    <div className={classNames(diffSummaryCloseStyles({ variant }), className)} {...props}>
      <Icon icon="mdi:close" size={1} />
    </div>
  );
}
