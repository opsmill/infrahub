import { cva, type VariantProps } from "class-variance-authority";
import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
  composeRenderProps,
} from "react-aria-components";

import { Spinner } from "@/shared/components/ui/spinner";
import { classNames } from "@/shared/utils/common";

import { focusVisibleStyle } from "./style-rac";

const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center gap-2 whitespace-nowrap",
    "rounded-lg border text-sm outline-none",
    "shadow-[0px_3px_6px_-2px_rgba(0,0,0,0.02),0px_1px_1px_rgba(0,0,0,0.04)]",
    "transition-all duration-150 ease-out",
    "data-disabled:pointer-events-none data-disabled:cursor-default data-disabled:opacity-60 data-disabled:shadow-none",
    "data-pending:cursor-default data-pending:select-none",
    "data-pressed:scale-95 data-pressed:shadow-none data-pressed:duration-75",
    "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: [
          "inset-shadow-[0_-1px_0_rgba(255,255,255,0.15),0_1px_0_rgba(255,255,255,0.15)] border-cyan-800 bg-gradient-to-b from-cyan-900 via-cyan-700 to-cyan-800 text-white",
          "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
        ],
        "primary-outline": [
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] border-cyan-700 bg-gradient-to-b from-stone-100 to-white text-cyan-700",
          "data-hovered:from-neutral-100",
        ],
        danger: [
          "inset-shadow-[0_-1px_0_rgba(255,255,255,0.15),0_1px_0_rgba(255,255,255,0.15)] border-red-700 bg-gradient-to-b from-red-800 via-red-600 to-red-700 text-white",
          "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
        ],
        "danger-outline": [
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] border-red-200 bg-gradient-to-b from-stone-100 to-white text-red-600",
          "data-hovered:from-red-50",
        ],
        warning: [
          "inset-shadow-[0_-1px_0_rgba(255,255,255,0.15),0_1px_0_rgba(255,255,255,0.15)] border-yellow-600 bg-gradient-to-b from-yellow-700 via-yellow-500 to-yellow-600 text-white",
          "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
        ],
        active: [
          "inset-shadow-[0_-1px_0_rgba(255,255,255,0.15),0_1px_0_rgba(255,255,255,0.15)] border-green-700 bg-gradient-to-b from-green-800 via-green-600 to-green-700 text-white",
          "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
        ],
        outline: [
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] border-neutral-200 bg-gradient-to-b from-stone-100 to-white text-stone-800",
          "data-hovered:from-neutral-100",
        ],
        ghost: [
          "border-transparent text-stone-800 shadow-none",
          "data-hovered:bg-neutral-200/50",
          "data-pressed:bg-neutral-200",
        ],
      },
      size: {
        default: "h-9 px-4",
        xs: "h-7 gap-1 px-2",
        sm: "h-8 gap-1.5 px-2.5",
        icon: "h-7 w-7 rounded-full",
        square: "h-9 w-9",
        "square-sm": "h-8 w-8",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
);

export interface ButtonProps extends AriaButtonProps, VariantProps<typeof buttonVariants> {
  isDisabledAndFocusable?: boolean /** Uses isPending internally to keep the button hoverable/focusable while appearing disabled. Useful for tooltip triggers. */;
}

export function Button({ variant, size, isDisabledAndFocusable, ...props }: ButtonProps) {
  return (
    <AriaButton
      slot={null}
      {...props}
      isPending={isDisabledAndFocusable || props.isPending}
      className={composeRenderProps(props.className, (className, { isPending }) =>
        classNames(
          focusVisibleStyle,
          buttonVariants({ variant, size, className }),
          isPending && !isDisabledAndFocusable && "text-transparent",
          isDisabledAndFocusable && "opacity-60 shadow-none"
        )
      )}
    >
      {composeRenderProps(props.children, (children, { isPending }) => (
        <>
          {isPending && !isDisabledAndFocusable && <Spinner className="absolute" />}
          {children}
        </>
      ))}
    </AriaButton>
  );
}

export interface LinkButtonProps extends AriaLinkProps, VariantProps<typeof buttonVariants> {}

export function LinkButton({ variant, size, ...props }: LinkButtonProps) {
  return (
    <AriaLink
      {...props}
      className={composeRenderProps(props.className, (className) =>
        classNames(focusVisibleStyle, buttonVariants({ variant, size, className }))
      )}
    />
  );
}

export { buttonVariants };
