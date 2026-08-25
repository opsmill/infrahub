import type React from "react";

import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  ref?: React.Ref<HTMLInputElement>;
}

export function Input({ className, ref, ...props }: InputProps) {
  return <input ref={ref} className={classNames(inputStyle, className)} {...props} />;
}

export interface MultilineInputProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  ref?: React.Ref<HTMLTextAreaElement>;
}

// Input look-alike that wraps and grows with its content instead of clipping
// long values at the right edge.
export function MultilineInput({ className, ref, ...props }: MultilineInputProps) {
  return (
    <textarea
      ref={ref}
      rows={1}
      className={classNames(inputStyle, "field-sizing-content max-h-40 resize-none", className)}
      {...props}
    />
  );
}
