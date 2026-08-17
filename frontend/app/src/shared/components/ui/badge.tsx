import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { classNames } from "@/shared/utils/common";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-1.5 py-0.5 font-semibold text-xs",
  {
    variants: {
      variant: {
        white: "border-transparent bg-content text-foreground dark:bg-white/5",
        gray: "border-transparent bg-content-strong text-foreground dark:bg-white/10",
        "dark-gray": "border-transparent bg-gray-300 text-foreground dark:bg-white/20",
        green:
          "border-transparent bg-green-700/10 text-green-900 dark:bg-green-400/20 dark:text-green-300",
        red: "border-transparent bg-danger-surface text-danger",
        blue: "border-transparent bg-custom-blue-700/10 text-custom-blue-700 dark:bg-custom-blue-500/30 dark:text-custom-blue-300",
        yellow:
          "border-transparent bg-yellow-100 text-yellow-900 dark:bg-yellow-400/20 dark:text-yellow-300",
        purple:
          "border-transparent bg-purple-100 text-purple-800 dark:bg-purple-400/20 dark:text-purple-300",
        "gray-outline": "border-border-strong bg-content text-foreground-muted dark:bg-transparent",
        "lightgray-outline": "bg-content text-subtle-muted dark:bg-transparent",
        "blue-outline":
          "border-custom-blue-700 bg-content text-custom-blue-700 dark:border-custom-blue-500 dark:bg-transparent dark:text-custom-blue-300",
        "yellow-outline":
          "border-yellow-100 bg-content text-yellow-900 dark:border-yellow-400/30 dark:bg-transparent dark:text-yellow-300",
        "green-outline": "border-2 border-green-500 text-green-700 dark:text-green-400",
        "red-outline": "border-2 border-danger text-danger",
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
