import { CheckIcon } from "lucide-react";
import {
  ListBox as AriaListBox,
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  type ListBoxProps as AriaListBoxProps,
  composeRenderProps,
} from "react-aria-components";

import { disabledStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

export interface ListBoxProps<T> extends AriaListBoxProps<T> {
  emptyMessage?: string;
}

export function ListBox<T extends object>({ className, emptyMessage, ...props }: ListBoxProps<T>) {
  return (
    <AriaListBox
      shouldFocusOnHover
      className={classNames("no-scrollbar max-h-[inherit] overflow-auto p-1 pb-1.5", className)}
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
      className={classNames(
        disabledStyle,
        "relative flex cursor-pointer select-none outline-hidden"
      )}
      {...props}
    >
      {composeRenderProps(
        children,
        (children, { isFocused, isSelected, isPressed, selectionMode }) => (
          <>
            {isFocused && (
              <span
                className={classNames(
                  "absolute inset-0 translate-y-0.75 rounded-lg border-stone-400 border-b bg-button-edge-gradient shadow-xs",
                  isPressed && "shadow-none"
                )}
              />
            )}

            <div
              className={classNames(
                "flex w-full items-center gap-2 rounded-lg border border-transparent px-2 py-1 text-sm transition-transform duration-100 will-change-transform",
                isFocused && "border-stone-300 bg-white",
                isPressed && "translate-y-0.75",
                selectionMode !== "none" && "pl-8",
                className
              )}
            >
              {isSelected && <CheckIcon className="absolute left-2 size-4" />}
              {children}
            </div>
          </>
        )
      )}
    </AriaListBoxItem>
  );
}
