import { ButtonHTMLAttributes, forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { classNames } from "../../utils/common";
import { Tooltip, TooltipProps } from "../ui/tooltip";

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-custom-blue-500 focus-visible:ring-offset-2 disabled:opacity-60",
  {
    variants: {
      variant: {
        primary: "text-white bg-custom-blue-600 shadow hover:bg-custom-blue-600/90",
        outline: "border bg-custom-white shadow-sm hover:bg-gray-100",
        ghost: "hover:bg-gray-100",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-7 px-2 text-sm",
        icon: "h-7 w-7 rounded-full",
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
    VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => {
    return (
      <button
        className={classNames(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    );
  }
);

interface ButtonWithTooltipProps extends ButtonProps {
  tooltipContent?: TooltipProps["content"];
  tooltipEnabled?: TooltipProps["enabled"];
}

export const ButtonWithTooltip = ({
  tooltipContent,
  tooltipEnabled,
  ...props
}: ButtonWithTooltipProps) => (
  <Tooltip enabled={tooltipEnabled} content={tooltipContent}>
    <Button {...props} />
  </Tooltip>
);
