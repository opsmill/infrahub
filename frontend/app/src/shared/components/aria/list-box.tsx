import { CheckIcon, LoaderIcon } from "lucide-react";
import {
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  ListBoxLoadMoreItem as AriaListBoxLoadMoreItem,
  type ListBoxLoadMoreItemProps as AriaListBoxLoadMoreItemProps,
  type ListBoxProps as AriaListBoxProps,
} from "react-aria-components";

import { disabledStyle } from "@/shared/components/style-rac";
import { PushableItem, pushableItemContainerStyle } from "@/shared/components/ui/pushable-item";
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

export function ListBoxItem<T extends object>({
  children,
  className,
  textValue,
  ...props
}: AriaListBoxItemProps<T>) {
  return (
    <AriaListBoxItem
      textValue={textValue || (typeof children === "string" ? children : undefined)}
      className={classNames(disabledStyle, pushableItemContainerStyle)}
      {...props}
    >
      {(renderProps) => (
        <PushableItem
          variant="ghost"
          isElevated={renderProps.isFocused}
          isPressed={renderProps.isPressed}
          className={classNames(
            renderProps.selectionMode !== "none" && "pl-8",
            typeof className === "function"
              ? className({ ...renderProps, defaultClassName: undefined })
              : className
          )}
        >
          {renderProps.isSelected && <CheckIcon className="absolute left-2 size-4" />}
          {typeof children === "function" ? children(renderProps) : children}
        </PushableItem>
      )}
    </AriaListBoxItem>
  );
}

export function ListBoxLoadMoreItem({ ...props }: AriaListBoxLoadMoreItemProps) {
  return (
    <AriaListBoxLoadMoreItem {...props}>
      <PushableItem variant="ghost" className="text-stone-400">
        <LoaderIcon className="size-3.5 animate-spin" /> loading...
      </PushableItem>
    </AriaListBoxLoadMoreItem>
  );
}
