import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { Col, type ColProps } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

export const TaskHomepageColumn = ({ className, ...props }: ColProps) => {
  return (
    <Col
      className={classNames("items-start gap-1.5 rounded-xl bg-gray-50 p-2", className)}
      {...props}
    />
  );
};

const taskHomepageColumnHeaderVariants = cva(
  "mb-0.5 inline-flex items-center rounded-md px-2 py-1 font-semibold text-xs",
  {
    variants: {
      variant: {
        gray: "bg-gray-100 text-gray-900",
        green: "bg-green-700/10 text-green-900",
        red: "bg-red-100 text-red-900",
        blue: "bg-custom-blue-700/10 text-custom-blue-700",
        yellow: "bg-yellow-100 text-yellow-900",
      },
    },
    defaultVariants: {
      variant: "gray",
    },
  }
);

export interface TaskHomepageColumnHeaderProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof taskHomepageColumnHeaderVariants> {}

export const TaskHomepageColumnHeader = ({
  className,
  variant,
  ...props
}: TaskHomepageColumnHeaderProps) => {
  return (
    <span
      className={classNames(taskHomepageColumnHeaderVariants({ variant }), className)}
      {...props}
    />
  );
};
