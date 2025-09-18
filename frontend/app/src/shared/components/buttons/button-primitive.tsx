import { cva, type VariantProps } from "class-variance-authority";
import { type ButtonHTMLAttributes, forwardRef } from "react";
import { Link, type LinkProps } from "react-router";

import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { Tooltip, type TooltipProps } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-sm border border-transparent font-medium text-sm disabled:cursor-not-allowed disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "bg-custom-blue-700 text-white shadow-sm enabled:hover:bg-custom-blue-700/90",
        "primary-outline":
          "border-custom-blue-700 bg-white text-custom-blue-700 shadow-xs enabled:hover:bg-gray-100",
        danger: "bg-red-500 text-white shadow-sm enabled:hover:bg-red-500/90",
        warning: "bg-yellow-500 text-white shadow-sm enabled:hover:bg-yellow-500/90",
        active: "bg-green-600 text-white shadow-sm enabled:hover:bg-green-600/90",
        "active-outline": "border-green-600 bg-white shadow-xs enabled:hover:bg-gray-100",
        outline: "border-gray-200 bg-white shadow-xs enabled:hover:bg-gray-100",
        dark: "bg-gray-200 shadow-xs enabled:hover:bg-gray-300",
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
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, type = "button", children, isLoading, ...props }, ref) => {
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
);

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
  side?: TooltipProps["side"];
}

export const ButtonWithTooltip = forwardRef<HTMLButtonElement, ButtonWithTooltipProps>(
  ({ tooltipContent, tooltipEnabled, side, ...props }, ref) => (
    <Tooltip enabled={tooltipEnabled} content={tooltipContent} side={side}>
      <Button ref={ref} {...props} />
    </Tooltip>
  )
);

export interface LinkButtonProps extends LinkProps, VariantProps<typeof buttonVariants> {}

export const LinkButton = forwardRef<HTMLAnchorElement, LinkButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <Link
        ref={ref}
        className={classNames(focusVisibleStyle, buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  }
);
