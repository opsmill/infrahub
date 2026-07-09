import type React from "react";

import { GripVerticalIcon } from "lucide-react";
import {
  DropIndicator,
  GridList as AriaGridList,
  type DropTarget,
  type DroppableCollectionReorderEvent,
  GridListItem as AriaGridListItem,
  type GridListItemProps as AriaGridListItemProps,
  type GridListProps as AriaGridListProps,
  type Key,
  useDragAndDrop,
} from "react-aria-components";
import { cn, tv } from "tailwind-variants";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Button } from "../button/button";

function reorderItems<T extends { id: Key }>(
  items: T[],
  event: DroppableCollectionReorderEvent,
): T[] {
  const { keys, target } = event;
  const moved = items.filter((item) => keys.has(item.id));
  const rest = items.filter((item) => !keys.has(item.id));

  const targetItem = rest.find((item) => item.id === target.key);
  if (!targetItem) {
    return items;
  }

  const targetIndex = rest.indexOf(targetItem);
  const insertIndex = target.dropPosition === "before" ? targetIndex : targetIndex + 1;
  return [...rest.slice(0, insertIndex), ...moved, ...rest.slice(insertIndex)];
}

export interface SortableListProps<T extends { id: Key }> extends Omit<
  AriaGridListProps<T>,
  "items" | "children" | "dragAndDropHooks"
> {
  items: T[];
  onReorder: (items: T[]) => void;
  children: (item: T) => React.ReactNode;
}

function SortableDropIndicator({ target }: { target: DropTarget }) {
  return (
    // -mt-px offsets the line's own height so this in-flow row adds no space, keeping siblings put.
    <DropIndicator
      target={target}
      className="mx-2 -mt-px h-px rounded-full bg-cyan-600 shadow-[0_0_6px_1px_rgba(6,182,212,0.55)] outline-hidden"
    />
  );
}

export function SortableList<T extends { id: Key }>({
  items,
  onReorder,
  children,
  ...props
}: SortableListProps<T>) {
  const { dragAndDropHooks } = useDragAndDrop({
    getItems: (keys) => [...keys].map((key) => ({ "text/plain": String(key) })),
    onReorder: (event) => {
      onReorder(reorderItems(items, event));
    },
    renderDropIndicator: (target) => <SortableDropIndicator target={target} />,
  });

  return (
    <AriaGridList items={items} dragAndDropHooks={dragAndDropHooks} {...props}>
      {children}
    </AriaGridList>
  );
}

const sortableItemStyles = tv({
  base: [
    "flex cursor-grab items-center gap-2 rounded-lg border border-transparent p-1 text-sm text-stone-600 outline-hidden select-none",
    "data-hovered:bg-stone-700/10 data-hovered:text-stone-800",
    "data-selected:bg-stone-700/10 data-selected:text-stone-800",
    "data-dragging:cursor-grabbing",
    "data-disabled:pointer-events-none data-disabled:opacity-50",
  ],
  variants: {
    isDragging: { true: "opacity-50" },
  },
});

export interface SortableItemProps extends AriaGridListItemProps {
  ref?: React.Ref<HTMLDivElement>;
}

export function SortableItem({ children, className, ref, ...props }: SortableItemProps) {
  return (
    <AriaGridListItem
      ref={ref}
      className={composeAriaClassName(className, ({ isDragging }) =>
        cn(focusVisibleStyle, sortableItemStyles({ isDragging })),
      )}
      {...props}
    >
      {(renderProps) => (
        <>
          <Button
            slot="drag"
            variant="ghost"
            shape="square"
            size="xxs"
            aria-label="Reorder"
            className="text-stone-400"
          >
            <GripVerticalIcon className="size-4" />
          </Button>
          {typeof children === "function" ? children(renderProps) : children}
        </>
      )}
    </AriaGridListItem>
  );
}
