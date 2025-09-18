import { forwardRef, type InputHTMLAttributes } from "react";

import { focusVisibleStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>((props, ref) => {
  const { className, onChange, disabled, ...propsToPass } = props;

  return (
    <input
      ref={ref}
      type="checkbox"
      disabled={disabled}
      onChange={onChange}
      className={classNames(
        "focus:ring-0 focus:ring-offset-0",
        focusVisibleStyle,
        "h-4 w-4 cursor-pointer rounded-sm border-gray-300 bg-gray-100 text-custom-blue-800 disabled:cursor-not-allowed disabled:text-gray-300",
        className
      )}
      data-cy="checkbox"
      {...propsToPass}
    />
  );
});
