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
