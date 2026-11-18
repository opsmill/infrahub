import { CheckIcon, LoaderIcon } from "lucide-react";
import React from "react";
import {
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  ListBoxLoadMoreItem as AriaListBoxLoadMoreItem,
  type ListBoxLoadMoreItemProps as AriaListBoxLoadMoreItemProps,
  type ListBoxProps as AriaListBoxProps,
  ListLayout,
  Virtualizer,
} from "react-aria-components";
import { tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

const DEFAULT_ROW_HEIGHT = 30;

export type SelectionIndicator = "checkmark" | "highlight" | "none";

const SelectionIndicatorContext = React.createContext<SelectionIndicator>("checkmark");

const listBoxStyles = tv({
  base: "no-scrollbar max-h-[inherit] overflow-auto outline-hidden",
  variants: {
    // The 4px inset is baked in here so call sites never add `p-1` themselves.
    // When virtualized it comes from the Virtualizer's layoutOptions.padding instead
    // CSS padding on the scroll container desyncs the virtualizer's absolute layout math and clips the last rows.
    virtualized: { false: "p-1" },
  },
});

export interface ListBoxProps<T> extends AriaListBoxProps<T> {
  emptyMessage?: React.ReactNode;
  selectionIndicator?: SelectionIndicator;
  virtualized?: boolean;
}

export function ListBox<T extends object>({
  className,
  emptyMessage,
  selectionIndicator = "checkmark",
  virtualized = false,
  ...props
}: ListBoxProps<T>) {
  const listBox = (
    <SelectionIndicatorContext.Provider value={selectionIndicator}>
      <AriaListBox
        shouldFocusOnHover
        className={composeAriaClassName(className, listBoxStyles({ virtualized }))}
        renderEmptyState={
          emptyMessage === undefined
            ? undefined
            : () => <div className="px-2 py-1 text-sm text-subtle-muted">{emptyMessage}</div>
        }
        {...props}
      />
    </SelectionIndicatorContext.Provider>
  );

  if (!virtualized) {
    return listBox;
  }

  return (
    <Virtualizer
      layout={ListLayout}
      layoutOptions={{
        rowHeight: DEFAULT_ROW_HEIGHT,
        loaderHeight: DEFAULT_ROW_HEIGHT,
        padding: 4,
      }}
    >
      {listBox}
    </Virtualizer>
  );
}

const listBoxItemStyles = tv({
  base: [
    "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-sm text-subtle outline-hidden",
    "data-disabled:pointer-events-none data-disabled:opacity-50",
  ],
  variants: {
    isFocused: {
      true: "bg-highlight text-highlight-foreground",
    },
    isSelected: {
      true: "",
    },
    selectionIndicator: {
      checkmark: "",
      highlight: "",
      none: "",
    },
  },
  compoundVariants: [
    {
      isSelected: true,
      selectionIndicator: "highlight",
      class: "bg-selected text-selected-foreground shadow-selected",
    },
    {
      isFocused: true,
      isSelected: true,
      selectionIndicator: "highlight",
      class: "bg-selected-highlight",
    },
  ],
});

export interface ListBoxItemProps<T> extends AriaListBoxItemProps<T> {
  ref?: React.Ref<HTMLDivElement>;
}

export function ListBoxItem<T extends object>({
  children,
  className,
  textValue,
  ref,
  ...props
}: ListBoxItemProps<T>) {
  const selectionIndicator = React.use(SelectionIndicatorContext);
  return (
    <AriaListBoxItem
      ref={ref}
      textValue={textValue || (typeof children === "string" ? children : undefined)}
      className={composeAriaClassName(className, ({ isFocused, isSelected }) =>
        listBoxItemStyles({ isFocused, isSelected, selectionIndicator })
      )}
      {...props}
    >
      {(renderProps) => (
        <>
          {typeof children === "function" ? children(renderProps) : children}
          {renderProps.isSelected && selectionIndicator === "checkmark" && (
            <CheckIcon className="ml-auto size-4 shrink-0" />
          )}
        </>
      )}
    </AriaListBoxItem>
  );
}

const listBoxLoadMoreStyles = tv({
  extend: listBoxItemStyles,
  base: "text-subtle-muted",
});

export function ListBoxLoadMoreItem({ className, ...props }: AriaListBoxLoadMoreItemProps) {
  return (
    <AriaListBoxLoadMoreItem className={listBoxLoadMoreStyles({ className })} {...props}>
      <LoaderIcon className="size-3.5 animate-spin" /> loading...
    </AriaListBoxLoadMoreItem>
  );
}
