import { forwardRef, InputHTMLAttributes } from "react";
import { classNames } from "../../utils/common";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={classNames(
          "flex w-full rounded-md border border-gray-300 bg-custom-white p-2 text-sm placeholder:text-gray-400 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-custom-blue-600 focus-visible:border-custom-blue-600 disabled:cursor-not-allowed disabled:bg-gray-100",
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
