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

import { focusVisibleStyle } from "@/shared/components/style-rac";
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
      <TagList className="inline-flex items-center gap-2">
        <TagList items={items} renderEmptyState={renderEmptyState}>
          {children}
        </TagList>
      </TagList>
    </TagGroup>
  );
}

const diffSummaryTagVariants = cva(
  [
    focusVisibleStyle,
    "inline-flex cursor-pointer items-center gap-1 rounded-full border border-transparent p-1 text-xs",
  ],
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

export interface DiffSummaryTagProps extends VariantProps<typeof diffSummaryTagVariants>, TagProps {
  count: number;
}

export function DiffSummaryTag({ count, variant, ...props }: DiffSummaryTagProps) {
  return (
    <Tag
      className={classNames(diffSummaryTagVariants({ variant }))}
      textValue={`diff ${variant} count`}
      {...props}
    >
      <DiffSummaryIcon variant={variant} />
      {count}
    </Tag>
  );
}

export function DiffSummaryIcon({
  variant,
  ...props
}: Pick<VariantProps<typeof diffSummaryTagVariants>, "variant">) {
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
