import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { classNames } from "@/shared/utils/common";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border border-gray-200 px-1.5 py-0.5 font-semibold text-xs",
  {
    variants: {
      variant: {
        white: "border-transparent bg-white text-gray-900",
        gray: "border-transparent bg-gray-100 text-gray-900",
        "dark-gray": "border-transparent bg-gray-300 text-gray-900",
        green: "border-transparent bg-green-700/10 text-green-900",
        red: "border-transparent bg-red-100 text-red-900",
        blue: "border-transparent bg-custom-blue-700/10 text-custom-blue-700",
        yellow: "border-transparent bg-yellow-100 text-yellow-900",
        purple: "border-transparent bg-purple-50 text-purple-900",
        "gray-outline": "border-gray-400 bg-white text-gray-700",
        "lightgray-outline": "border-gray-200 bg-white text-gray-500",
        "blue-outline": "border-custom-blue-700 bg-white text-custom-blue-700",
        "yellow-outline": "border-yellow-100 bg-white text-yellow-900",
        "green-outline": "border-2 border-green-500 text-green-700",
        "red-outline": "border-2 border-red-500 text-red-700",
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
