import * as React from "react";
import { tv, type VariantProps } from "tailwind-variants";

export const buttonVariants = tv({
  base: "inline-flex shrink-0 items-center justify-center whitespace-nowrap rounded-sm border border-transparent font-medium text-sm disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-custom-blue-700",
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
});

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  ref?: React.Ref<HTMLButtonElement>;
}

export function Button({
  className,
  variant,
  size,
  type = "button",
  ref,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={buttonVariants({ variant, size, className })}
      type={type}
      ref={ref}
      {...props}
    >
      {children}
    </button>
  );
}
