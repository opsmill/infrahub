import { CheckIcon, LoaderIcon } from "lucide-react";
import type React from "react";
import {
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  ListBoxLoadMoreItem as AriaListBoxLoadMoreItem,
  type ListBoxLoadMoreItemProps as AriaListBoxLoadMoreItemProps,
  type ListBoxProps as AriaListBoxProps,
  composeRenderProps,
} from "react-aria-components";

import { disabledStyle } from "@/shared/components/aria/style-rac";
import { classNames } from "@/shared/utils/common";

export interface ListBoxProps<T> extends AriaListBoxProps<T> {
  emptyMessage?: string;
}

export function ListBox<T extends object>({ className, emptyMessage, ...props }: ListBoxProps<T>) {
  return (
    <AriaListBox
      shouldFocusOnHover
      className={classNames("no-scrollbar max-h-[inherit] overflow-auto", className)}
      renderEmptyState={
        emptyMessage
          ? () => <div className="px-2 py-1.5 text-neutral-600 text-sm">{emptyMessage}</div>
          : undefined
      }
      {...props}
    />
  );
}

const listBoxItemBaseStyle =
  "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-sm text-stone-600 outline-hidden";
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
      className={composeRenderProps(className, (className, { isSelected, isFocused }) =>
        classNames(
          disabledStyle,
          listBoxItemBaseStyle,
          isFocused && "bg-stone-700/10 text-stone-800",
          isSelected && selectionIndicator === "none" && "bg-stone-700/10",
          className
        )
      )}
      {...props}
    >
      {(renderProps) => (
        <>
          {typeof children === "function" ? children(renderProps) : children}
          {renderProps.isSelected && selectionIndicator === "checkmark" && (
            <CheckIcon className={classNames("ml-auto size-4 shrink-0")} />
          )}
        </>
      )}
    </AriaListBoxItem>
  );
}

export function ListBoxLoadMoreItem({ className, ...props }: AriaListBoxLoadMoreItemProps) {
  return (
    <AriaListBoxLoadMoreItem
      className={classNames(listBoxItemBaseStyle, "text-stone-400", className)}
      {...props}
    >
      <LoaderIcon className="size-3.5 animate-spin" /> loading...
    </AriaListBoxLoadMoreItem>
  );
}
