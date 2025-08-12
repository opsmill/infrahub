import { Spinner } from "@/shared/components/ui/spinner";
import { focusVisibleStyle } from "@/shared/components/ui/style";
import { Tooltip, TooltipProps } from "@/shared/components/ui/tooltip";
import { classNames } from "@/shared/utils/common";
import { type VariantProps, cva } from "class-variance-authority";
import { ButtonHTMLAttributes, forwardRef } from "react";
import { Link, LinkProps } from "react-router";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-sm text-sm font-medium disabled:opacity-60 disabled:cursor-not-allowed border border-transparent",
  {
    variants: {
      variant: {
        primary: "text-white bg-custom-blue-700 shadow-sm enabled:hover:bg-custom-blue-700/90",
        "primary-outline":
          "text-custom-blue-700 border-custom-blue-700 bg-white shadow-xs enabled:hover:bg-gray-100",
        danger: "text-white bg-red-500 shadow-sm enabled:hover:bg-red-500/90",
        warning: "text-white bg-yellow-500 shadow-sm enabled:hover:bg-yellow-500/90",
        active: "text-white bg-green-600 shadow-sm enabled:hover:bg-green-600/90",
        "active-outline": "bg-white border-green-600 shadow-xs enabled:hover:bg-gray-100",
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
