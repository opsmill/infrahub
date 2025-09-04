import { cva, VariantProps } from "class-variance-authority";
import { Button as AriaButton, ButtonProps as AriaButtonProps } from "react-aria-components";

import { focusVisibleStyle } from "@/shared/components/style-rac";
import { classNames } from "@/shared/utils/common";

const toolbarButtonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap h-7 bg-white px-2 py-1 rounded-lg disabled:opacity-60 disabled:cursor-not-allowed border border-transparent",
  {
    variants: {
      variant: {
        default: "border-neutral-200 hover:bg-neutral-50",
        danger: "text-red-600 border-red-200 hover:bg-neutral-50",
        ghost: "text-neutral-600 bg-transparent hover:bg-neutral-200/80",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface ToolbarButtonProps
  extends AriaButtonProps,
    VariantProps<typeof toolbarButtonVariants> {}

export function ToolbarButton({ className, variant, ...props }: ToolbarButtonProps) {
  return (
    <AriaButton
      className={classNames(focusVisibleStyle, toolbarButtonVariants({ variant }), className)}
      {...props}
    />
  );
}
