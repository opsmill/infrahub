import { forwardRef, HTMLAttributes } from "react";
import { classNames } from "../../utils/common";

export const Card = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={classNames("bg-custom-white rounded-lg border border-gray-300 p-3", className)}
      {...props}
    />
  )
);

export const CardWithBorder = forwardRef<HTMLDivElement, HTMLAttributes<HTMLDivElement>>(
  ({ children, className }) => {
    return (
      <div className={classNames("border rounded-lg", className)}>
        <div className="border rounded-md m-3 overflow-hidden">{children}</div>
      </div>
    );
  }
);
