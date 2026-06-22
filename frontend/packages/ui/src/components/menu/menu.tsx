import type React from "react";

import {
  Header as AriaHeader,
  Menu as AriaMenu,
  MenuItem as AriaMenuItem,
  type MenuItemProps as AriaMenuItemProps,
  type MenuProps as AriaMenuProps,
  MenuSection as AriaMenuSection,
  type MenuSectionProps as AriaMenuSectionProps,
  MenuTrigger as AriaMenuTrigger,
  Collection,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Tooltip, type TooltipProps } from "../tooltip/tooltip";

export const MenuTrigger = AriaMenuTrigger;

export interface MenuProps<T> extends AriaMenuProps<T> {}
export const Menu = <T extends object>({ className, ...props }: MenuProps<T>) => {
  return (
    <AriaMenu
      className={composeAriaClassName(className, (resolvedClassName) =>
        cn(
          "no-scrollbar max-h-[inherit] overflow-auto p-1 outline-hidden",
          "space-y-0.5 *:[[role='group']:not(:last-child)]:mb-2",
          resolvedClassName,
        ),
      )}
      {...props}
    />
  );
};

export interface MenuItemProps extends AriaMenuItemProps {
  tooltip?: TooltipProps["message"];
  side?: TooltipProps["placement"];
}

export const MenuItem = ({
  tooltip,
  side,
  children,
  className,
  textValue,
  ...props
}: MenuItemProps) => {
  if (tooltip !== undefined) {
    return (
      <MenuItemWithTooltip
        tooltip={tooltip}
        side={side}
        className={className}
        textValue={textValue ?? (typeof children === "string" ? children : undefined)}
        {...props}
      >
        {children}
      </MenuItemWithTooltip>
    );
  }

  return (
    <AriaMenuItem
      textValue={textValue ?? (typeof children === "string" ? children : undefined)}
      className={composeAriaClassName(className, (resolvedClassName) =>
        cn(
          "data-disabled:pointer-events-none data-disabled:opacity-50",
          "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-md border border-transparent bg-white px-2 py-1 text-sm text-stone-600 shadow-sm outline-hidden transition-colors",
          "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:pointer-events-none [&_svg]:shrink-0",
          "data-focused:border-sky-200 data-focused:bg-sky-50 data-focused:text-sky-700",
          resolvedClassName,
        ),
      )}
      {...props}
    >
      {children}
    </AriaMenuItem>
  );
};

export interface MenuSectionProps<T> extends AriaMenuSectionProps<T> {
  title?: React.ReactNode;
}
export const MenuSection = <T extends object>({
  className,
  title,
  children,
  ...props
}: MenuSectionProps<T>) => {
  return (
    <AriaMenuSection className={cn("flex flex-col gap-0.5", className)} {...props}>
      {title && <AriaHeader className="px-1 text-stone-500 text-xs">{title}</AriaHeader>}
      <Collection items={props.items}>{children}</Collection>
    </AriaMenuSection>
  );
};

interface MenuItemWithTooltipProps extends MenuItemProps {}

function MenuItemWithTooltip({
  tooltip,
  side = "left",
  isDisabled,
  className,
  children,
  ...props
}: MenuItemWithTooltipProps) {
  return (
    <MenuItem
      isDisabled={isDisabled}
      className={composeAriaClassName(className, "data-disabled:pointer-events-auto")}
      {...props}
    >
      {(renderProps) => (
        <Tooltip
          message={isDisabled ? tooltip : undefined}
          placement={side}
          className="z-100001"
          nonInteractiveTrigger
        >
          <span className="flex w-full items-center gap-[inherit]">
            {typeof children === "function" ? children(renderProps) : children}
          </span>
        </Tooltip>
      )}
    </MenuItem>
  );
}
