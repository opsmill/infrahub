import type React from "react";

import { CheckIcon, LoaderIcon } from "lucide-react";
import {
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  ListBoxLoadMoreItem as AriaListBoxLoadMoreItem,
  type ListBoxLoadMoreItemProps as AriaListBoxLoadMoreItemProps,
  type ListBoxProps as AriaListBoxProps,
} from "react-aria-components";
import { cn, tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export interface ListBoxProps<T> extends AriaListBoxProps<T> {
  emptyMessage?: string;
}

export function ListBox<T extends object>({ className, emptyMessage, ...props }: ListBoxProps<T>) {
  return (
    <AriaListBox
      shouldFocusOnHover
      className={composeAriaClassName(className, (resolvedClassName) =>
        cn("no-scrollbar max-h-[inherit] overflow-auto", resolvedClassName),
      )}
      renderEmptyState={
        emptyMessage
          ? () => <div className="px-2 py-1.5 text-neutral-600 text-sm">{emptyMessage}</div>
          : undefined
      }
      {...props}
    />
  );
}

const listBoxItemStyles = tv({
  base: [
    "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-sm text-stone-600 outline-hidden",
    "data-disabled:pointer-events-none data-disabled:opacity-50",
  ],
  variants: {
    isFocused: { true: "bg-stone-700/10 text-stone-800" },
    isSelected: { true: "bg-stone-700/10" },
  },
});

export interface ListBoxItemProps<T> extends AriaListBoxItemProps<T> {
  ref?: React.Ref<HTMLDivElement>;
  selectionIndicator?: "checkmark" | "none";
}

export function ListBoxItem<T extends object>({
  children,
  className,
  textValue,
  ref,
  selectionIndicator = "checkmark",
  ...props
}: ListBoxItemProps<T>) {
  return (
    <AriaListBoxItem
      ref={ref}
      textValue={textValue || (typeof children === "string" ? children : undefined)}
      className={composeAriaClassName(className, ({ isFocused, isSelected }) =>
        listBoxItemStyles({
          isFocused,
          isSelected: isSelected && selectionIndicator === "none",
        }),
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
