import React from "react";
import { cva, VariantProps } from "class-variance-authority";
import { classNames } from "../../utils/common";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "border-transparent bg-gray-100 text-gray-900",
        blue: "border-transparent bg-custom-blue-700/10 text-custom-blue-700",
        green: "border-transparent bg-green-100 text-green-900",
        yellow: "border-transparent bg-yellow-100 text-yellow-900",
        red: "border-transparent bg-red-50 text-red-900",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = ({ className = "", variant, ...props }: BadgeProps) => {
  return <div className={classNames(badgeVariants({ variant }), className)} {...props} />;
};

export { Badge };
