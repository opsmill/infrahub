import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  DialogTrigger as AriaDialogTrigger,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
} from "react-aria-components";
import { tv } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export const PopoverTrigger = AriaDialogTrigger;

const popoverStyles = tv({
  base: [
    "z-50 rounded-xl border border-neutral-300 bg-stone-100/70 shadow-md outline-hidden backdrop-blur-lg duration-100",
    "data-[placement=bottom]:slide-in-from-top-10 data-[placement=left]:slide-in-from-right-2 data-[placement=right]:slide-in-from-left-2 data-[placement=top]:slide-in-from-bottom-2",
  ],
  variants: {
    isEntering: {
      true: "fade-in-0 zoom-in-95 animate-in",
    },
    isExiting: {
      true: "fade-out-0 zoom-out-95 animate-out",
    },
  },
});

const popoverDialogStyles = tv({
  base: "outline-hidden",
});

export interface PopoverProps extends AriaPopoverProps {}

export function Popover({ className, ...props }: PopoverProps) {
  return (
    <AriaPopover
      offset={4}
      className={composeAriaClassName(className, (renderProps) => popoverStyles(renderProps))}
      {...props}
    />
  );
}

export function PopoverDialog({ className, ...props }: AriaDialogProps) {
  return <AriaDialog className={popoverDialogStyles({ className })} {...props} />;
}
