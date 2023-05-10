import { ChangeEventHandler } from "react";

type CheckboxProps = {
  enabled?: boolean;
  onChange?: ChangeEventHandler;
};

export const Checkbox = (props: CheckboxProps) => {
  const { enabled, onChange } = props;

  return (
    <input
      type="checkbox"
      checked={enabled ?? false}
      onChange={onChange}
      className="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 focus:ring-2 cursor-pointer"
    />
  );
};
