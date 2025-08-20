import { classNames } from "@/shared/utils/common";
import React from "react";

interface PulseProps extends React.HTMLAttributes<HTMLSpanElement> {}

export function Pulse({ className, ...props }: PulseProps) {
  return (
    <span className={classNames("absolute flex h-2 w-2", className)} {...props}>
      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-custom-blue-500 opacity-75"></span>
      <span className="relative inline-flex rounded-full h-2 w-2 bg-custom-blue-700"></span>
    </span>
  );
}
