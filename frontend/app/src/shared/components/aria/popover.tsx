import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  DialogTrigger as AriaDialogTrigger,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
  composeRenderProps,
} from "react-aria-components";

import { classNames } from "@/shared/utils/common";

export const PopoverTrigger = AriaDialogTrigger;

export interface PopoverProps extends AriaPopoverProps {}

export function Popover({ className, offset = 4, ...props }: PopoverProps) {
  return (
    <AriaPopover
      offset={offset}
      className={composeRenderProps(className, (className) =>
        classNames(
          "z-50 rounded-xl border border-neutral-200 bg-white shadow-md outline-hidden duration-50 dark:border-gray-700 dark:bg-gray-800",
          "data-entering:fade-in-0 data-entering:zoom-in-95 data-entering:animate-in",
          "data-exiting:fade-out-0 data-exiting:zoom-out-95 data-exiting:animate-out",
          "data-[placement=bottom]:slide-in-from-top-2 data-[placement=left]:slide-in-from-right-2 data-[placement=right]:slide-in-from-left-2 data-[placement=top]:slide-in-from-bottom-2",
          className
        )
      )}
      {...props}
    />
  );
}

export function PopoverDialog({ className, ...props }: AriaDialogProps) {
  return <AriaDialog className={classNames("outline-hidden", className)} {...props} />;
}
