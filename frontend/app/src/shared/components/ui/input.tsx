import React from "react";

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

const supportsFieldSizing = typeof CSS !== "undefined" && CSS.supports("field-sizing", "content");

// Input look-alike that wraps and grows with its content instead of clipping
// long values at the right edge.
export function MultilineInput({ className, ref, ...props }: MultilineInputProps) {
  const innerRef = React.useRef<HTMLTextAreaElement>(null);

  // Fallback for browsers without `field-sizing: content` (Firefox < 152,
  // Safari < 26.2), where the textarea would stay one row tall and hide the
  // wrapped value. Runs on every render to track controlled value updates.
  React.useLayoutEffect(() => {
    if (supportsFieldSizing) return;
    const element = innerRef.current;
    if (!element) return;
    element.style.height = "auto";
    const borderHeight = element.offsetHeight - element.clientHeight;
    element.style.height = `${element.scrollHeight + borderHeight}px`;
  });

  return (
    <textarea
      ref={(element) => {
        innerRef.current = element;
        if (typeof ref === "function") ref(element);
        else if (ref) ref.current = element;
      }}
      rows={1}
      className={classNames(inputStyle, "field-sizing-content max-h-40 resize-none", className)}
      {...props}
    />
  );
}
