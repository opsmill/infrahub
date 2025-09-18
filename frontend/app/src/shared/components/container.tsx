import type React from "react";

import { classNames } from "@/shared/utils/common";

export interface RowProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Row({ className, ...props }: RowProps) {
  return <div className={classNames("flex items-center gap-2", className)} {...props} />;
}

export function Col({ className, ...props }: RowProps) {
  return <div className={classNames("flex flex-col items-stretch gap-2", className)} {...props} />;
}
