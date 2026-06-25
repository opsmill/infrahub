import { ChevronRightIcon } from "lucide-react";
import React from "react";
import {
  Header as AriaHeader,
  Menu as AriaMenu,
  MenuItem as AriaMenuItem,
  type MenuItemProps as AriaMenuItemProps,
  type MenuProps as AriaMenuProps,
  MenuSection as AriaMenuSection,
  type MenuSectionProps as AriaMenuSectionProps,
  MenuTrigger as AriaMenuTrigger,
  SubmenuTrigger as AriaSubmenuTrigger,
  Collection,
} from "react-aria-components";
import { type VariantProps, cn, tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Tooltip, type TooltipProps } from "../tooltip/tooltip";

export const MenuTrigger = AriaMenuTrigger;
export const SubmenuTrigger = AriaSubmenuTrigger;

const menuItemStyles = tv({
  base: [
    "flex min-w-40 cursor-pointer select-none items-center gap-2 border border-transparent rounded-lg px-2 py-1 text-sm text-stone-600 outline-hidden",
    "data-disabled:pointer-events-none data-disabled:opacity-50",
    "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  variants: {
    variant: {
      action: [
        "[&:not(:last-child)]:mb-0.5 bg-white shadow-sm transition-colors",
        "data-focused:border-sky-200 data-focused:bg-sky-50 data-focused:text-sky-700",
      ],
      picker: ["rounded-lg", "data-focused:bg-stone-700/10 data-focused:text-stone-800"],
    },
  },
  defaultVariants: { variant: "action" },
});

type MenuVariants = VariantProps<typeof menuItemStyles>;

const MenuVariantContext = React.createContext<MenuVariants["variant"]>("action");

export interface MenuProps<T> extends AriaMenuProps<T>, MenuVariants {}

export const Menu = <T extends object>({ className, variant, ...props }: MenuProps<T>) => {
  const resolvedVariant = variant ?? React.use(MenuVariantContext);

  return (
    <MenuVariantContext.Provider value={resolvedVariant}>
      <AriaMenu
        className={composeAriaClassName(
          className,
          cn(
            "no-scrollbar max-h-[inherit] overflow-auto p-1 outline-hidden",
            "*:[[role='group']:not(:last-child)]:mb-2",
          ),
        )}
        {...props}
      />
    </MenuVariantContext.Provider>
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

  const variant = React.use(MenuVariantContext);

  return (
    <AriaMenuItem
      textValue={textValue ?? (typeof children === "string" ? children : undefined)}
      className={composeAriaClassName(className, menuItemStyles({ variant }))}
      {...props}
    >
      {(renderProps) => (
        <>
          {typeof children === "function" ? children(renderProps) : children}
          {renderProps.hasSubmenu && <ChevronRightIcon className="ml-auto" />}
        </>
      )}
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
    <AriaMenuSection className={cn("flex flex-col", className)} {...props}>
      {title && <AriaHeader className="px-1 text-stone-500 text-xs mb-0.5">{title}</AriaHeader>}
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
