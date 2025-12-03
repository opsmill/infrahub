import { cva, type VariantProps } from "class-variance-authority";
import type React from "react";

import { Col, type ColProps } from "@/shared/components/container";
import { classNames } from "@/shared/utils/common";

export const TaskHomepageColumn = ({ className, children, ...props }: ColProps) => {
  return (
    <Col
      className={classNames(
        "min-h-0 flex-1 items-start gap-1.5 overflow-hidden rounded-xl bg-gray-50 p-2 dark:bg-slate-800",
        className
      )}
      {...props}
    >
      {children}
    </Col>
  );
};

const taskHomepageColumnHeaderVariants = cva(
  "mb-0.5 inline-flex items-center rounded-md px-2 py-1 font-semibold text-xs",
  {
    variants: {
      variant: {
        gray: "bg-gray-100 text-gray-900 dark:bg-gray-700 dark:text-gray-100",
        green: "bg-green-700/10 text-green-900 dark:bg-green-900/30 dark:text-green-400",
        red: "bg-red-100 text-red-900 dark:bg-red-900/30 dark:text-red-400",
        blue: "bg-custom-blue-700/10 text-custom-blue-700 dark:bg-custom-blue-900/30 dark:text-custom-blue-400",
        yellow: "bg-yellow-100 text-yellow-900 dark:bg-yellow-900/30 dark:text-yellow-400",
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
