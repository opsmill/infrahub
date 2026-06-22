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
import { cn, tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

const listBoxLayoutOptions = { rowHeight: 30, loaderHeight: 30, padding: 4 };

export function ListBoxVirtualizer({ children }: { children: React.ReactNode }) {
  return (
    <Virtualizer layout={ListLayout} layoutOptions={listBoxLayoutOptions}>
      {children}
    </Virtualizer>
  );
}

export type SelectionIndicator = "checkmark" | "highlight" | "none";

const SelectionIndicatorContext = React.createContext<SelectionIndicator>("checkmark");

export interface ListBoxProps<T> extends AriaListBoxProps<T> {
  emptyMessage?: React.ReactNode;
  selectionIndicator?: SelectionIndicator;
}

export function ListBox<T extends object>({
  className,
  emptyMessage,
  selectionIndicator = "checkmark",
  ...props
}: ListBoxProps<T>) {
  return (
    <SelectionIndicatorContext.Provider value={selectionIndicator}>
      <AriaListBox
        shouldFocusOnHover
        className={composeAriaClassName(className, (resolvedClassName) =>
          cn("no-scrollbar max-h-[inherit] overflow-auto outline-hidden", resolvedClassName),
        )}
        renderEmptyState={
          emptyMessage === undefined
            ? undefined
            : () => <div className="px-2 py-1 text-neutral-600 text-sm">{emptyMessage}</div>
        }
        {...props}
      />
    </SelectionIndicatorContext.Provider>
  );
}

const listBoxItemStyles = tv({
  base: [
    "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-sm text-stone-600 outline-hidden",
    "data-disabled:pointer-events-none data-disabled:opacity-50",
  ],
  variants: {
    isFocused: { true: "bg-stone-700/10 text-stone-800" },
  },
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
        cn(
          listBoxItemStyles({ isFocused }),
          isSelected && selectionIndicator === "highlight" && "bg-stone-700/10  text-stone-800",
        ),
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
  base: "text-stone-400",
});

export function ListBoxLoadMoreItem({ className, ...props }: AriaListBoxLoadMoreItemProps) {
  return (
    <AriaListBoxLoadMoreItem className={listBoxLoadMoreStyles({ className })} {...props}>
      <LoaderIcon className="size-3.5 animate-spin" /> loading...
    </AriaListBoxLoadMoreItem>
  );
}
