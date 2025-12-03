import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { classNames } from "@/shared/utils/common";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border border-gray-200 px-1.5 py-0.5 font-semibold text-xs dark:border-gray-700",
  {
    variants: {
      variant: {
        white: "border-transparent bg-white text-gray-900 dark:bg-gray-800 dark:text-gray-100",
        gray: "border-transparent bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100",
        "dark-gray":
          "border-transparent bg-gray-300 text-gray-900 dark:bg-gray-600 dark:text-gray-100",
        green:
          "border-transparent bg-green-700/10 text-green-900 dark:bg-green-900/30 dark:text-green-400",
        red: "border-transparent bg-red-100 text-red-900 dark:bg-red-700/40 dark:text-red-300",
        blue: "border-transparent bg-custom-blue-700/10 text-custom-blue-700 dark:bg-custom-blue-900/30 dark:text-custom-blue-400",
        yellow:
          "border-transparent bg-yellow-100 text-yellow-900 dark:bg-yellow-700/40 dark:text-yellow-300",
        purple:
          "border-transparent bg-purple-50 text-purple-900 dark:bg-purple-900/30 dark:text-purple-400",
        "gray-outline":
          "border-gray-400 bg-white text-gray-700 dark:border-gray-500 dark:bg-gray-800 dark:text-gray-300",
        "lightgray-outline":
          "border-gray-200 bg-white text-gray-500 dark:border-gray-600 dark:bg-gray-800 dark:text-gray-400",
        "blue-outline":
          "border-custom-blue-700 bg-white text-custom-blue-700 dark:bg-gray-800",
        "yellow-outline":
          "border-yellow-100 bg-white text-yellow-900 dark:border-yellow-700 dark:bg-gray-800 dark:text-yellow-400",
        "green-outline":
          "border-2 border-green-500 text-green-700 dark:text-green-400",
        "red-outline": "border-2 border-red-500 text-red-700 dark:text-red-400",
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
