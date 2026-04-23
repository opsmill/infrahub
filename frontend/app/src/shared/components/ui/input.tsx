import type React from "react";

import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  ref?: React.Ref<HTMLInputElement>;
}

export function Input({ className, ref, ...props }: InputProps) {
  return <input ref={ref} className={classNames(inputStyle, className)} {...props} />;
}
