import { forwardRef, type InputHTMLAttributes } from "react";

import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => {
  return <input ref={ref} className={classNames(inputStyle, className)} {...props} />;
});
