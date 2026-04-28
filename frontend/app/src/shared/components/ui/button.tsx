import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";
import { Link, type LinkProps } from "react-router";

import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { Tooltip, type TooltipProps } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-sm border border-transparent font-medium text-sm disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-custom-blue-700 text-white shadow-sm hover:bg-custom-blue-700/90",
        "primary-outline":
          "border-custom-blue-700 bg-white text-custom-blue-700 shadow-xs hover:bg-gray-100",
        danger: "bg-red-500 text-white shadow-sm hover:bg-red-500/90",
        warning: "bg-yellow-500 text-white shadow-sm hover:bg-yellow-500/90",
        active: "bg-green-600 text-white shadow-sm hover:bg-green-600/90",
        "active-outline": "border-green-600 bg-white shadow-xs hover:bg-gray-100",
        outline: "border-gray-200 bg-white shadow-xs hover:bg-gray-100",
        dark: "bg-gray-200 shadow-xs hover:bg-gray-300",
        ghost: "hover:bg-gray-100",
      },
      size: {
        default: "h-9 px-4 py-2",
        xs: "h-7 px-2 text-xs",
        sm: "h-8 px-2 text-sm",
        icon: "h-7 w-7 rounded-full",
        square: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "default",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  ref?: React.Ref<HTMLButtonElement>;
  isLoading?: boolean;
}

export function Button({
  className,
  variant,
  size,
  type = "button",
  children,
  isLoading,
  ref,
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={classNames(
        "relative",
        focusVisibleStyle,
        buttonVariants({ variant, size, className }),
        isLoading && "text-transparent"
      )}
      ref={ref}
      {...props}
    >
      {isLoading && <Spinner className="absolute" />}
      {children}
    </button>
  );
}

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
  side?: TooltipProps["side"];
}

export function ButtonWithTooltip({
  tooltipContent,
  tooltipEnabled,
  side = "top",
  disabled,
  onClick,
  className,
  ref,
  ...props
}: ButtonWithTooltipProps) {
  // Native `disabled` kills pointer events, so the tooltip never fires on the
  // button itself. Use aria-disabled so the button stays hoverable and the
  // tooltip anchors directly to it (no extra wrapper that would shift side/align).
  const isDisabled = !!disabled;

  return (
    <Tooltip enabled={tooltipEnabled} content={tooltipContent} side={side}>
      <Button
        ref={ref}
        {...props}
        aria-disabled={isDisabled || undefined}
        onClick={isDisabled ? undefined : onClick}
        className={classNames(isDisabled && "cursor-not-allowed opacity-60", className)}
      />
    </Tooltip>
  );
}

export interface LinkButtonProps extends LinkProps, VariantProps<typeof buttonVariants> {
  ref?: React.Ref<HTMLAnchorElement>;
}

export function LinkButton({ className, variant, size, ref, ...props }: LinkButtonProps) {
  return (
    <Link
      ref={ref}
      className={classNames(focusVisibleStyle, buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}
