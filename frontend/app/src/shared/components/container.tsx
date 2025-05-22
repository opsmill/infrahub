import { classNames } from "@/shared/utils/common";
import React from "react";

export interface RowProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Row({ children, className, ...props }: RowProps) {
  return (
    <div className={classNames("flex items-center gap-2", className)} {...props}>
      {children}
    </div>
  );
}

export function Col({ className, ...props }: RowProps) {
  return <Row className={classNames("flex-col", className)} {...props} />;
}
