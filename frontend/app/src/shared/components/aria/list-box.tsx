import { Icon } from "@iconify-icon/react";
import {
  ListBoxItem as AriaListBoxItem,
  type ListBoxItemProps as AriaListBoxItemProps,
  composeRenderProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export const ListBoxItem = <T extends object>({
  className,
  children,
  ...props
}: AriaListBoxItemProps<T>) => {
  return (
    <AriaListBoxItem
      textValue={props.textValue || (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          "relative flex w-full cursor-default select-none items-center rounded-xs px-2 py-1.5 text-sm outline-hidden",
          "data-disabled:pointer-events-none data-disabled:opacity-50",
          "data-focused:bg-gray-100",
          "data-selection-mode:pl-8",
          className
        )
      )}
      {...props}
    >
      {composeRenderProps(children, (children, renderProps) => (
        <>
          {renderProps.isSelected && (
            <span className="absolute left-2 flex size-4 items-center justify-center">
              <Icon icon="mdi:check" />
            </span>
          )}
          {children}
        </>
      ))}
    </AriaListBoxItem>
  );
};
