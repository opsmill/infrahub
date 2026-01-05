import type React from "react";

import { classNames } from "@/shared/utils/common";

interface PulseProps extends React.HTMLAttributes<HTMLSpanElement> {}

export function Pulse({ className, ...props }: PulseProps) {
  return (
    <span className={classNames("absolute flex h-2 w-2", className)} {...props}>
      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-custom-blue-500 opacity-75"></span>
      <span className="relative inline-flex h-2 w-2 rounded-full bg-custom-blue-700"></span>
    </span>
  );
}
