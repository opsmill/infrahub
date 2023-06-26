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
      className="w-4 h-4 text-custom-blue bg-gray-100 border-gray-300 rounded focus:ring-custom-blue dark:focus:ring-custom-blue focus:ring-2 cursor-pointer"
    />
  );
};
