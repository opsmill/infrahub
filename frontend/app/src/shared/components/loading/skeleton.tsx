import type { HTMLAttributes } from "react";

import { classNames } from "@/shared/utils/common";

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={classNames("animate-skeleton rounded-md bg-custom-blue-700/20", className)}
      {...props}
    />
  );
}
