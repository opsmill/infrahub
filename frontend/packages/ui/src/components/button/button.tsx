import type { RefAttributes } from "react";

import {
  Button as AriaButton,
  type ButtonProps as AriaButtonProps,
  Link as AriaLink,
  type LinkProps as AriaLinkProps,
  composeRenderProps,
} from "react-aria-components";
import { cn, tv, type VariantProps } from "tailwind-variants";

import { focusVisibleStyle } from "../../styles/focus-visible";
import { composeAriaClassName } from "../../utils/compose-aria-class-name";
import { Spinner } from "../spinner/spinner";

const buttonVariants = tv({
  base: [
    focusVisibleStyle,
    "relative inline-flex shrink-0 cursor-pointer items-center justify-center whitespace-nowrap",
    "rounded-xl border text-sm outline-none",
    "shadow-[0px_3px_6px_-2px_rgba(0,0,0,0.02),0px_1px_1px_rgba(0,0,0,0.04)]",
    "transition-all duration-150 ease-out",
    "data-disabled:pointer-events-none data-disabled:cursor-default data-disabled:opacity-60 data-disabled:shadow-none",
    "data-pending:cursor-default data-pending:select-none",
    "data-pressed:scale-97 data-pressed:shadow-none data-pressed:duration-75",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-3.5",
  ],
  variants: {
    variant: {
      primary: [
        "border-cyan-800 bg-gradient-to-b from-cyan-800 to-cyan-700 text-white inset-shadow-[0_1px_0_rgba(255,255,255,0.15)]",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      "primary-outline": [
        "border-cyan-700 bg-gradient-to-b from-stone-100 to-white text-cyan-700 inset-shadow-[0_1px_0_rgba(255,255,255,0.9)]",
        "data-hovered:from-neutral-100",
      ],
      danger: [
        "border-rose-700 bg-gradient-to-b from-rose-700 to-rose-600 text-white inset-shadow-[0_1px_0_rgba(255,255,255,0.15)]",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      "danger-outline": [
        "border-rose-200 bg-gradient-to-b from-stone-100 to-white text-rose-600 inset-shadow-[0_1px_0_rgba(255,255,255,0.9)]",
        "data-hovered:from-rose-50",
      ],
      warning: [
        "border-amber-600 bg-gradient-to-b from-amber-600 to-amber-500 text-white inset-shadow-[0_1px_0_rgba(255,255,255,0.15)]",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      active: [
        "border-emerald-700 bg-gradient-to-b from-emerald-700 to-emerald-700 text-white inset-shadow-[0_1px_0_rgba(255,255,255,0.15)]",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      outline: [
        "bg-gradient-to-b from-stone-100 to-white text-foreground inset-shadow-[0_1px_0_rgba(255,255,255,0.9)]",
        "data-hovered:from-neutral-100",
      ],
      ghost: [
        "border-transparent text-foreground shadow-none",
        "data-hovered:bg-neutral-600/10",
        "data-pressed:bg-neutral-200",
      ],
      input: [
        "bg-white text-foreground",
        "shadow-[0_2px_4px_rgba(0,0,0,0.04)]",
        "data-pressed:scale-100",
      ],
    },
    size: {
      xxs: "h-6 text-xs",
      xs: "h-7",
      sm: "h-8",
      md: "h-9",
    },
    shape: {
      default: "rounded-lg",
      square: "aspect-square rounded-lg",
      circle: "aspect-square rounded-full",
    },
  },
  compoundVariants: [
    { variant: "input", class: "rounded-xl" }, // Beat shape=default's rounded-lg to match the input's rounded-xl
    { variant: "input", shape: "default", class: "justify-start" },
    { shape: "default", size: "xxs", class: "gap-1 px-1.5" },
    { shape: "default", size: "xs", class: "gap-1 px-2" },
    { shape: "default", size: "sm", class: "gap-1.5 px-2" },
    { shape: "default", size: "md", class: "gap-2 px-3" },
  ],
  defaultVariants: {
    variant: "primary",
    size: "md",
    shape: "default",
  },
});

export interface ButtonProps
  extends AriaButtonProps, VariantProps<typeof buttonVariants>, RefAttributes<HTMLButtonElement> {
  /** Uses isPending internally to keep the button hoverable/focusable while appearing disabled. Useful for tooltip triggers. */
  isDisabledAndFocusable?: boolean;
}

export function Button({ variant, size, shape, isDisabledAndFocusable, ...props }: ButtonProps) {
  return (
    <AriaButton
      slot={null}
      {...props}
      isPending={isDisabledAndFocusable || props.isPending}
      className={composeAriaClassName(props.className, ({ isPending }) =>
        cn(
          buttonVariants({ variant, size, shape }),
          isPending && !isDisabledAndFocusable && "text-transparent",
          isDisabledAndFocusable && "opacity-60 shadow-none",
        ),
      )}
    >
      {composeRenderProps(props.children, (children, { isPending }) => (
        <>
          {isPending && !isDisabledAndFocusable && <Spinner className="absolute inset-0 m-auto" />}
          {children}
        </>
      ))}
    </AriaButton>
  );
}

export interface LinkButtonProps extends AriaLinkProps, VariantProps<typeof buttonVariants> {}

export function LinkButton({ variant, size, shape, ...props }: LinkButtonProps) {
  return (
    <AriaLink
      {...props}
      className={composeAriaClassName(props.className, buttonVariants({ variant, size, shape }))}
    />
  );
}

export { buttonVariants };
