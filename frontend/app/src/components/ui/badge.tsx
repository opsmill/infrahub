import { classNames } from "@/utils/common";
import { cva, VariantProps } from "class-variance-authority";
import React from "react";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-1.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        white: "border-transparent bg-custom-white text-gray-900",
        gray: "border-transparent bg-gray-100 text-gray-900",
        "dark-gray": "border-transparent bg-gray-300 text-gray-900",
        green: "border-transparent bg-green-200 text-green-900",
        red: "border-transparent bg-red-100 text-red-900",
        blue: "border-transparent bg-custom-blue-700/10 text-custom-blue-700",
        yellow: "border-transparent bg-yellow-100 text-yellow-900",
        purple: "border-transparent bg-purple-50 text-purple-900",
        "green-outline": "bg-custom-white border-2 text-green-700 border-green-500",
        "red-outline": "bg-custom-white border-2 text-red-700 border-red-500",
        "blue-outline": "bg-custom-white border-custom-blue-700 text-custom-blue-700",
        "yellow-outline": "bg-custom-white border-yellow-100 text-yellow-900",
      },
    },
    defaultVariants: {
      variant: "gray",
    },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

const Badge = ({ className = "", variant, ...props }: BadgeProps) => {
  return <span className={classNames(badgeVariants({ variant }), className)} {...props} />;
};

export { Badge };
