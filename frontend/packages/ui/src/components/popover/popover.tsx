import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  DialogTrigger as AriaDialogTrigger,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
} from "react-aria-components";
import { cn } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export const PopoverTrigger = AriaDialogTrigger;

export interface PopoverProps extends AriaPopoverProps {}

export function Popover({ className, offset = 4, ...props }: PopoverProps) {
  return (
    <AriaPopover
      offset={offset}
      className={composeAriaClassName(
        className,
        cn(
          "z-50 rounded-xl border border-neutral-300 bg-stone-100/70 shadow-md outline-hidden backdrop-blur-lg duration-50",
          "data-entering:fade-in-0 data-entering:zoom-in-95 data-entering:animate-in",
          "data-exiting:fade-out-0 data-exiting:zoom-out-95 data-exiting:animate-out",
          "data-[placement=bottom]:slide-in-from-top-2 data-[placement=left]:slide-in-from-right-2 data-[placement=right]:slide-in-from-left-2 data-[placement=top]:slide-in-from-bottom-2"
        )
      )}
      {...props}
    />
  );
}

export function PopoverDialog({ className, ...props }: AriaDialogProps) {
  return <AriaDialog className={cn("outline-hidden", className)} {...props} />;
}
