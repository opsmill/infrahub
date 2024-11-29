import { inputStyle } from "@/components/ui/style";
import { classNames } from "@/utils/common";
import { InputHTMLAttributes, forwardRef } from "react";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => {
  return <input ref={ref} className={classNames(inputStyle, className)} {...props} />;
});
