import { focusStyle } from "@/components/ui/style";
import { Tooltip, TooltipProps } from "@/components/ui/tooltip";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { classNames } from "@/utils/common";
import { cva, type VariantProps } from "class-variance-authority";
import { ButtonHTMLAttributes, forwardRef } from "react";
import { Link, LinkProps } from "react-router-dom";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium disabled:opacity-60 disabled:cursor-disabled",
  {
    variants: {
      variant: {
        primary: "text-white bg-custom-blue-700 shadow hover:bg-custom-blue-700/90",
        danger: "text-white bg-red-400 shadow hover:bg-red-300",
        active: "text-white bg-green-500 shadow hover:bg-green-500/90",
        outline: "border bg-custom-white shadow-sm hover:bg-gray-100",
        ghost: "hover:bg-gray-100",
      },
      size: {
        default: "h-9 px-4 py-2",
        xs: "h-7 px-2 text-xs",
        sm: "h-7 px-2 text-sm",
        icon: "h-7 w-7 rounded-full",
        square: "h-9 w-9 rounded-md",
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
        className={classNames(focusStyle, buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}>
        {isLoading && <LoadingScreen hideText size={8} />}
        {!isLoading && children}
      </button>
    );
  }
);

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
}

export const ButtonWithTooltip = forwardRef<HTMLButtonElement, ButtonWithTooltipProps>(
  ({ tooltipContent, tooltipEnabled, ...props }, ref) => (
    <Tooltip enabled={tooltipEnabled} content={tooltipContent}>
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
        className={classNames(focusStyle, buttonVariants({ variant, size, className }))}
        {...props}
      />
    );
  }
);
