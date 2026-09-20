import { GripVerticalIcon } from "lucide-react";
import React from "react";
import {
  GridList as AriaGridList,
  GridListItem as AriaGridListItem,
  type GridListItemProps as AriaGridListItemProps,
  type GridListProps as AriaGridListProps,
  DropIndicator,
  type DroppableCollectionReorderEvent,
  type DropTarget,
  type Key,
  useDragAndDrop,
} from "react-aria-components";
import { tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Button } from "../button/button";

function reorderItems<T>(
  items: T[],
  event: DroppableCollectionReorderEvent,
  getId: (item: T) => Key
): T[] {
  const { keys, target } = event;
  const moved = items.filter((item) => keys.has(getId(item)));
  const rest = items.filter((item) => !keys.has(getId(item)));

  const targetItem = rest.find((item) => getId(item) === target.key);
  if (!targetItem) {
    return items;
  }

  const targetIndex = rest.indexOf(targetItem);
  const insertIndex = target.dropPosition === "before" ? targetIndex : targetIndex + 1;
  return [...rest.slice(0, insertIndex), ...moved, ...rest.slice(insertIndex)];
}

export interface SortableListProps<T extends object>
  extends Omit<AriaGridListProps<T>, "items" | "children" | "dragAndDropHooks"> {
  items: T[];
  onReorder: (items: T[]) => void;
  children: (item: T) => React.ReactNode;
}

function SortableDropIndicator({ target }: { target: DropTarget }) {
  return (
    // -mt-px offsets the line's own height so this in-flow row never shifts siblings.
    <DropIndicator
      target={target}
      className="-mt-px h-px rounded-full bg-cyan-700 opacity-0 shadow-[0_0_2px_1px_rgba(6,182,212,0.25)] outline-hidden transition-opacity data-drop-target:opacity-100"
    />
  );
}

export function SortableList<T extends object>({
  items,
  onReorder,
  children,
  ...props
}: SortableListProps<T>) {
  const getItemId = (item: T): Key => {
    const element = children(item);
    const id = React.isValidElement<{ id?: Key }>(element) ? element.props.id : undefined;
    return id ?? (item as { id: Key }).id;
  };

  const { dragAndDropHooks } = useDragAndDrop({
    getItems: (keys) => [...keys].map((key) => ({ "text/plain": String(key) })),
    onReorder: (event) => {
      onReorder(reorderItems(items, event, getItemId));
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
    "flex cursor-grab select-none items-center gap-1.5 rounded-lg border border-transparent p-0.5 text-sm text-subtle outline-hidden",
    "data-focus-visible:bg-highlight data-focus-visible:text-foreground",
    "data-selected:bg-selected data-selected:text-foreground",
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
        sortableItemStyles({ isDragging })
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
            className="text-subtle-muted"
          >
            <GripVerticalIcon className="size-4" />
          </Button>
          {typeof children === "function" ? children(renderProps) : children}
        </>
      )}
    </AriaGridListItem>
  );
}
