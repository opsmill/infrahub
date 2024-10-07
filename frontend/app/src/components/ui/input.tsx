import { classNames } from "@/utils/common";
import { forwardRef, InputHTMLAttributes } from "react";
import { inputStyle } from "@/components/ui/style";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => {
  return <input ref={ref} className={classNames(inputStyle, className)} {...props} />;
});
