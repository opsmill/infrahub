import { ChangeEventHandler } from "react";

type CheckboxProps = {
  enabled?: boolean;
  onChange?: ChangeEventHandler;
  disabled?: boolean;
};

export const Checkbox = (props: CheckboxProps) => {
  const { enabled, onChange, disabled } = props;

  return (
    <input
      type="checkbox"
      checked={enabled ?? false}
      disabled={disabled}
      onChange={onChange}
      className="w-4 h-4 text-custom-blue-500 bg-gray-100 border-gray-300 rounded focus:ring-custom-blue-500 dark:focus:ring-custom-blue-500 focus:ring-2 cursor-pointer"
    />
  );
};
