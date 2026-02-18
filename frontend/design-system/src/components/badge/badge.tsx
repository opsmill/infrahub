import type React from "react";
import { cn, tv, type VariantProps } from "tailwind-variants";

export const badgeVariants = tv({
  base: "inline-flex items-center rounded-md border px-1.5 py-0.5 font-semibold text-xs",
  variants: {
    variant: {
      gray: "border-transparent bg-gray-100 text-gray-900",
      blue: "border-transparent bg-cyan-700/10 text-cyan-700",
      green: "border-transparent bg-green-100 text-green-900",
      yellow: "border-transparent bg-yellow-100 text-yellow-900",
      red: "border-transparent bg-red-50 text-red-900",

      "green-outline": "border-2 border-green-500 text-green-700",
      "red-outline": "border-2 border-red-500 text-red-700",
    },
  },
  defaultVariants: {
    variant: "gray",
  },
});

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export const Badge = ({ className, variant, ...props }: BadgeProps) => {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
};
