import { focusStyle } from "@/components/ui/style";
import { classNames } from "@/utils/common";
import { forwardRef, InputHTMLAttributes } from "react";

interface CheckboxProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>((props, ref) => {
  const {className, onChange, disabled, ...propsToPass } = props;

  return (
    <input
      ref={ref}
      type="checkbox"
      disabled={disabled}
      onChange={onChange}
      className={classNames(
        "focus:ring-0 focus:ring-offset-0",
        focusStyle,
        "w-4 h-4 text-custom-blue-800 disabled:text-gray-300 bg-gray-100 border-gray-300 rounded cursor-pointer disabled:cursor-not-allowed",
        className
      )}
      data-cy="checkbox"
      {...propsToPass}
    />
  );
});
