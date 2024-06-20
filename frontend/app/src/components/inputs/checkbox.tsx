import { focusStyle } from "@/components/ui/style";
import { classNames } from "@/utils/common";
import { ChangeEventHandler, forwardRef } from "react";

type CheckboxProps = {
  checked?: boolean;
  onChange?: ChangeEventHandler;
  disabled?: boolean;
  id?: string;
};

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>((props, ref) => {
  const { onChange, disabled, ...propsToPass } = props;

  return (
    <input
      ref={ref}
      type="checkbox"
      disabled={disabled}
      onChange={onChange}
      className={classNames(
        "focus:ring-0 focus:ring-offset-0",
        focusStyle,
        "w-4 h-4 text-custom-blue-800 disabled:text-gray-300 bg-gray-100 border-gray-300 rounded cursor-pointer disabled:cursor-not-allowed"
      )}
      data-cy="checkbox"
      {...propsToPass}
    />
  );
});
