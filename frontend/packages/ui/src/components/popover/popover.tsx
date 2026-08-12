import {
  Dialog as AriaDialog,
  type DialogProps as AriaDialogProps,
  DialogTrigger as AriaDialogTrigger,
  Popover as AriaPopover,
  type PopoverProps as AriaPopoverProps,
} from "react-aria-components";
import { tv, type VariantProps } from "tailwind-variants";

import { composeAriaClassName } from "../../utils/compose-aria-class-name";

export const PopoverTrigger = AriaDialogTrigger;

const popoverStyles = tv({
  base: [
    "z-50 rounded-xl border border-border-strong bg-stone-100/70 shadow-md outline-hidden backdrop-blur-lg duration-100",
    "data-[placement=bottom]:slide-in-from-top-10 data-[placement=left]:slide-in-from-right-2 data-[placement=right]:slide-in-from-left-2 data-[placement=top]:slide-in-from-bottom-2",
  ],
  variants: {
    isEntering: {
      true: "pointer-events-none animate-in fade-in-0 zoom-in-95",
    },
    isExiting: {
      true: "animate-out fade-out-0 zoom-out-95",
    },
    width: {
      trigger: "w-(--trigger-width)",
      "min-trigger": "min-w-(--trigger-width)",
      content: "",
    },
  },
});

const popoverDialogStyles = tv({
  base: "outline-hidden",
});

export interface PopoverProps
  extends AriaPopoverProps, Pick<VariantProps<typeof popoverStyles>, "width"> {}

export function Popover({ className, width = "content", ...props }: PopoverProps) {
  return (
    <AriaPopover
      offset={4}
      className={composeAriaClassName(className, (renderProps) =>
        popoverStyles({ ...renderProps, width }),
      )}
      {...props}
    />
  );
}

export function PopoverDialog({ className, ...props }: AriaDialogProps) {
  return <AriaDialog className={popoverDialogStyles({ className })} {...props} />;
}
