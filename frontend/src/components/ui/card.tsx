import { forwardRef, HTMLAttributes } from "react";
import { classNames } from "../../utils/common";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames("bg-custom-white rounded-lg border border-gray-300 p-4", className)}
      {...props}
    />
  )
);
