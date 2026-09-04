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
    "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  ],
  variants: {
    variant: {
      primary: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.15)] border-cyan-800 bg-gradient-to-b from-cyan-900 to-cyan-900/80 text-white",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      "primary-outline": [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] border-cyan-700 bg-gradient-to-b from-stone-100 to-white text-cyan-800 dark:text-cyan-600",
        "data-hovered:from-neutral-100",
        "dark:inset-shadow-[0_1px_0_rgba(255,255,255,0.12)] dark:from-stone-500/15 dark:to-stone-500/5",
        "dark:data-hovered:from-stone-500/25",
      ],
      danger: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.15)] border-rose-700 bg-gradient-to-b from-rose-700 to-rose-700/70 text-white",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      "danger-outline": [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] border-danger-surface bg-gradient-to-b from-stone-100 to-white text-danger",
        "data-hovered:from-rose-50",
        "dark:inset-shadow-[0_1px_0_rgba(255,255,255,0.12)] dark:from-stone-500/15 dark:to-stone-500/5",
        "dark:data-hovered:from-rose-500/15",
      ],
      warning: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.15)] border-amber-600 bg-gradient-to-b from-amber-600 to-amber-700/70 text-white",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      active: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.15)] border-emerald-700 bg-gradient-to-b from-emerald-700 to-emerald-800/70 text-white",
        "data-hovered:inset-shadow-[0_-2px_2px_rgba(255,255,255,0.15),0_2px_2px_rgba(255,255,255,0.15)]",
      ],
      outline: [
        "inset-shadow-[0_1px_0_rgba(255,255,255,0.9)] bg-gradient-to-b from-stone-100 to-white text-foreground",
        "dark:inset-shadow-[0_1px_0_rgba(255,255,255,0.07)] dark:border-stone-700 dark:from-stone-700/70 dark:to-stone-900",
        "data-hovered:from-neutral-100 dark:data-hovered:from-stone-700",
      ],
      ghost: [
        "border-transparent text-foreground shadow-none",
        "data-hovered:bg-border",
        "data-pressed:bg-border",
      ],
      input: [
        "border-input-border bg-input text-foreground shadow-input",
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
  extends AriaButtonProps,
    VariantProps<typeof buttonVariants>,
    RefAttributes<HTMLButtonElement> {
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
          isDisabledAndFocusable && "opacity-60 shadow-none"
        )
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
