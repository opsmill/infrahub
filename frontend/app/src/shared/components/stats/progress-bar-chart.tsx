import * as ProgressPrimitive from "@radix-ui/react-progress";
import type { HTMLAttributes } from "react";

import { classNames } from "@/shared/utils/common";

export const ProgressBar = ({ className, value, ...props }: ProgressPrimitive.ProgressProps) => (
  <ProgressPrimitive.Root
    className={classNames(
      "relative h-2 w-full overflow-hidden rounded-full bg-custom-blue-600/20",
      className
    )}
    {...props}
  >
    <ProgressPrimitive.Indicator
      className="h-full w-full flex-1 bg-custom-blue-600 transition-all"
      style={{ transform: `translateX(-${100 - (value || 0)}%)` }}
    />
  </ProgressPrimitive.Root>
);

const sanitizeProgressBarValue = (value: number) => {
  if (isNaN(value)) return 0;

  if (value > 100) return 100;

  return value;
};

interface ProgressBarChartProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
}

export default function ProgressBarChart({ value, className, ...props }: ProgressBarChartProps) {
  return (
    <div className={classNames("flex w-full items-center gap-2", className)} {...props}>
      <ProgressBar value={sanitizeProgressBarValue(value)} className="h-2 grow" />
      <span className="font-medium text-custom-blue-700">{value}%</span>
    </div>
  );
}
