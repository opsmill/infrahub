import { cva, type VariantProps } from "class-variance-authority";
import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

interface TaskHomepageColumnProps {
  children?: ReactNode;
  className?: string;
}

export const TaskHomepageColumn = ({ children, className }: TaskHomepageColumnProps) => {
  return (
    <div className={classNames("flex flex-col gap-4 rounded bg-gray-50 p-2", className)}>
      {children}
    </div>
  );
};

const headerVariant = cva(
  "inline-flex items-center rounded-md border border-transparent px-1.5 py-0.5 font-semibold text-xs",
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
    VariantProps<typeof headerVariant> {}

export const TaskHomepageColumnHeader = ({
  className = "",
  variant,
  ...props
}: TaskHomepageColumnHeaderProps) => {
  return <span className={classNames(headerVariant({ variant }), className)} {...props} />;
};
