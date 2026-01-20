import type React from "react";

import { classNames } from "@/shared/utils/common";

export interface RowProps extends React.HTMLAttributes<HTMLDivElement> {
  ref?: React.Ref<HTMLDivElement>;
}

export function Row({ className, ref, ...props }: RowProps) {
  return <div className={classNames("flex items-center gap-2", className)} ref={ref} {...props} />;
}

export interface ColProps extends React.HTMLAttributes<HTMLDivElement> {}

export function Col({ className, ...props }: ColProps) {
  return <div className={classNames("flex flex-col items-stretch gap-2", className)} {...props} />;
}
