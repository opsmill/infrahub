import type React from "react";

import { classNames } from "@/shared/utils/common";

export interface RowProps extends React.ComponentProps<"div"> {}

export function Row({ className, ...props }: RowProps) {
  return <div className={classNames("flex items-center gap-2", className)} {...props} />;
}

export interface ColProps extends React.ComponentProps<"div"> {}

export function Col({ className, ...props }: ColProps) {
  return <div className={classNames("flex flex-col items-stretch gap-2", className)} {...props} />;
}
