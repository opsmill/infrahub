import {
  Menu as AriaMenu,
  MenuItem as AriaMenuItem,
  MenuItemProps as AriaMenuItemProps,
  MenuProps as AriaMenuProps,
  MenuTrigger as AriaMenuTrigger,
  SubmenuTrigger as AriaSubmenuTrigger,
  PopoverProps,
  composeRenderProps,
} from "react-aria-components";

import { disabledStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";
import { SelectPopover } from "./select";

export const MenuTrigger = AriaMenuTrigger;

export const MenuSubTrigger = AriaSubmenuTrigger;

export const MenuPopover = ({ className, ...props }: PopoverProps) => {
  return (
    <SelectPopover
      className={composeRenderProps(className, (className) => classNames("w-auto", className))}
      {...props}
    />
  );
};

export const Menu = <T extends object>({ className, ...props }: AriaMenuProps<T>) => {
  return (
    <AriaMenu
      className={classNames(
        "max-h-[inherit] overflow-auto rounded-md outline outline-0 [clip-path:inset(0_0_0_0_round_calc(var(--radius)-2px))]",
        className
      )}
      {...props}
    />
  );
};

export const MenuItem = ({ children, className, ...props }: AriaMenuItemProps) => {
  return (
    <AriaMenuItem
      textValue={props.textValue || (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          "relative flex cursor-default select-none items-center gap-2 rounded-xs px-2 py-1.5 text-sm outline-hidden transition-colors",
          disabledStyle,
          "data-focused:bg-gray-100",
          className
        )
      )}
      {...props}
    >
      {children}
    </AriaMenuItem>
  );
};
