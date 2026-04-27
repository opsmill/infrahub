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
    "rounded-lg border text-sm outline-none transition-shadow",
    "before:pointer-events-none before:absolute before:inset-0 before:rounded-[inherit]",
    "data-disabled:pointer-events-none data-disabled:cursor-default data-disabled:opacity-60 data-disabled:shadow-none",
    "data-[pending]:cursor-default data-[pending]:select-none",
    "[&_svg:not([class*='size-'])]:size-4 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  {
    variants: {
      variant: {
        primary: [
          "border-custom-blue-800 bg-custom-blue-700 text-white",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.18)] shadow-custom-blue-900/25 shadow-xs",
          "data-hovered:bg-custom-blue-700/90",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.08)] data-pressed:shadow-none",
        ],
        "primary-outline": [
          "border-custom-blue-700 bg-gradient-to-b from-white to-custom-blue-1/40 text-custom-blue-700",
          "shadow-xs before:shadow-[inset_0_1px_0_rgba(255,255,255,0.9)]",
          "data-hovered:from-custom-blue-1/60 data-hovered:to-custom-blue-1/80",
          "data-pressed:shadow-none",
        ],
        danger: [
          "border-red-600 bg-red-500 text-white",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.18)] shadow-red-600/25 shadow-xs",
          "data-hovered:bg-red-500/90",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.08)] data-pressed:shadow-none",
        ],
        "danger-outline": [
          "border-red-200 bg-gradient-to-b from-white to-neutral-100 text-red-600",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] shadow-xs",
          "data-hovered:to-red-100/80",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.06)] data-pressed:shadow-none",
        ],
        warning: [
          "border-yellow-600 bg-yellow-500 text-white",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.18)] shadow-xs shadow-yellow-600/25",
          "data-hovered:bg-yellow-500/90",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.08)] data-pressed:shadow-none",
        ],
        active: [
          "border-green-700 bg-green-600 text-white",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.18)] shadow-green-700/25 shadow-xs",
          "data-hovered:bg-green-600/90",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.08)] data-pressed:shadow-none",
        ],
        outline: [
          "border-gray-300 bg-gradient-to-b from-white to-neutral-100 text-neutral-900",
          "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] shadow-xs",
          "data-hovered:to-neutral-200/60",
          "data-pressed:inset-shadow-[0_1px_0_rgba(0,0,0,0.06)] data-pressed:shadow-none",
        ],
        ghost: [
          "border-transparent text-neutral-900 data-hovered:bg-neutral-200/50 data-pressed:bg-neutral-200",
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
