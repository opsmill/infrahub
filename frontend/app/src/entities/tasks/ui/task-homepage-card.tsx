import type { ReactNode } from "react";

import { classNames } from "@/shared/utils/common";

interface TaskHomepageCardProps {
  children?: ReactNode;
  className?: string;
}

export const TaskHomepageCard = ({ children, className }: TaskHomepageCardProps) => {
  return (
    <div className={classNames("flex flex-col gap-2 rounded bg-white p-2 shadow", className)}>
      {children}
    </div>
  );
};
