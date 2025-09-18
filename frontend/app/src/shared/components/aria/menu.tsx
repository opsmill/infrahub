import { CopyIcon } from "lucide-react";
import {
  Header as AriaHeader,
  type HeadingProps as AriaHeadingProps,
  Menu as AriaMenu,
  MenuItem as AriaMenuItem,
  type MenuItemProps as AriaMenuItemProps,
  type MenuProps as AriaMenuProps,
  MenuSection as AriaMenuSection,
  type MenuSectionProps as AriaMenuSectionProps,
  MenuTrigger as AriaMenuTrigger,
  type PopoverProps as AriaPopoverProps,
  composeRenderProps,
} from "react-aria-components";

import { Popover } from "@/shared/components/aria/popover";
import { disabledStyle } from "@/shared/components/style-rac";
import { useCopyToClipboard } from "@/shared/hooks/useCopyToClipboard";
import { classNames } from "@/shared/utils/common";

export const MenuTrigger = AriaMenuTrigger;

export interface MenuPopoverProps extends AriaPopoverProps {}
export const MenuPopover = ({ className, ...props }: MenuPopoverProps) => {
  return (
    <Popover
      className={composeRenderProps(className, (className) => {
        return classNames("rounded-lg border-stone-200 bg-stone-100 p-1", className);
      })}
      {...props}
    />
  );
};

export interface MenuProps<T> extends AriaMenuProps<T> {}
export const Menu = <T extends object>({ className, ...props }: MenuProps<T>) => {
  return (
    <AriaMenu
      className={classNames(
        "max-h-[inherit] overflow-auto rounded-md outline-hidden",
        "*:[[role='group']:not(:last-child)]:mb-2",
        className
      )}
      {...props}
    />
  );
};

export interface MenuItemProps extends AriaMenuItemProps {}
export const MenuItem = ({ children, className, ...props }: MenuItemProps) => {
  return (
    <AriaMenuItem
      textValue={props.textValue || (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          disabledStyle,
          "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-md border border-transparent bg-white px-2 py-1 text-sm text-stone-600 outline-hidden transition-colors",
          "data-focused:border-stone-300",
          className
        )
      )}
      {...props}
    >
      {children}
    </AriaMenuItem>
  );
};

export interface MenuSectionProps<T> extends AriaMenuSectionProps<T> {}
export const MenuSection = <T extends object>({ className, ...props }: MenuSectionProps<T>) => {
  return <AriaMenuSection className={classNames("flex flex-col gap-0.5", className)} {...props} />;
};

export interface MenuHeaderProps extends AriaHeadingProps {}
export const MenuHeader = ({ className, ...props }: MenuHeaderProps) => {
  return <AriaHeader className={classNames("px-1 text-stone-500 text-xs", className)} {...props} />;
};

export interface CopyToClipboardMenuItemProps extends Omit<MenuItemProps, "onAction" | "children"> {
  textToCopy: string;
  children?: React.ReactNode;
}
export function CopyToClipboardMenuItem({
  textToCopy,
  children,
  ...props
}: CopyToClipboardMenuItemProps) {
  const { copyToClipboard } = useCopyToClipboard();
  return (
    <MenuItem onAction={() => copyToClipboard(textToCopy)} {...props}>
      <CopyIcon className="size-3" />
      {children}
    </MenuItem>
  );
}
