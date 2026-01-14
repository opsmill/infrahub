import { CheckIcon, LoaderIcon } from "lucide-react";
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
  "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-md border border-transparent px-2 py-1 text-sm text-stone-600 outline-hidden transition-colors";
export function ListBoxItem<T extends object>({
  children,
  className,
  textValue,
  ...props
}: AriaListBoxItemProps<T>) {
  return (
    <AriaListBoxItem
      textValue={textValue || (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          disabledStyle,
          listBoxItemBaseStyle,
          "data-focused:border-stone-100 data-focused:bg-white data-focused:shadow-sm",
          className
        )
      )}
      {...props}
    >
      {(renderProps) => (
        <>
          {renderProps.isSelected && <CheckIcon className="absolute left-2 size-4" />}
          {typeof children === "function" ? children(renderProps) : children}
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
