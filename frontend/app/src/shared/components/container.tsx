import { classNames } from "@/shared/utils/common";
import React from "react";

export interface RowProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
}

export function Row({ className, ...props }: RowProps) {
  return <div className={classNames("flex items-center gap-2", className)} {...props} />;
}

export function Col({ className, ...props }: RowProps) {
  return <div className={classNames("flex flex-col items-stretch gap-2", className)} {...props} />;
}
