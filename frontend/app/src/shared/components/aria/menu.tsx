import { CopyIcon } from "lucide-react";
import {
  Header as AriaHeader,
  Menu as AriaMenu,
  MenuItem as AriaMenuItem,
  type MenuItemProps as AriaMenuItemProps,
  type MenuProps as AriaMenuProps,
  MenuSection as AriaMenuSection,
  type MenuSectionProps as AriaMenuSectionProps,
  MenuTrigger as AriaMenuTrigger,
  type PopoverProps as AriaPopoverProps,
  Collection,
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
        return classNames("border-stone-200 bg-stone-100", className);
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
        "no-scrollbar max-h-[inherit] overflow-auto p-1 outline-hidden",
        "space-y-0.5 *:[[role='group']:not(:last-child)]:mb-2",
        className
      )}
      {...props}
    />
  );
};

export interface MenuItemProps extends AriaMenuItemProps {}

export const MenuItem = ({ children, className, textValue, ...props }: MenuItemProps) => {
  return (
    <AriaMenuItem
      textValue={textValue ?? (typeof children === "string" ? children : undefined)}
      className={composeRenderProps(className, (className) =>
        classNames(
          disabledStyle,
          "flex min-w-40 cursor-pointer select-none items-center gap-2 rounded-md border border-transparent bg-white px-2 py-1 text-sm text-stone-600 shadow-sm outline-hidden transition-colors",
          "data-focused:ring-1",
          className
        )
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
    <AriaMenuSection className={classNames("flex flex-col gap-0.5", className)} {...props}>
      {title && <AriaHeader className="px-1 text-stone-500 text-xs">{title}</AriaHeader>}
      <Collection items={props.items}>{children}</Collection>
    </AriaMenuSection>
  );
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
