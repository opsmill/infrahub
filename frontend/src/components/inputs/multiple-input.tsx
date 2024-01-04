import React from "react";
import { classNames } from "../../utils/common";
import { Badge } from "../display/badge";
import { SelectOption } from "./select";

type MultipleInputProps = {
  value: SelectOption[] | undefined;
  onChange: (item: SelectOption[] | undefined) => void;
  className?: string;
  disabled?: boolean;
};

// Forward ref used for Combobox.Input in Select
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
export const MultipleInput = React.forwardRef((props: MultipleInputProps, ref: any) => {
  const { className, onChange, value, disabled } = props;

  // Remove item from list
  const handleDelete = (item: SelectOption) => {
    const newValue = value?.filter((v: SelectOption) => v.id !== item.id);

    return onChange(newValue);
  };

  return (
    <div
      className={classNames(
        `flex flex-wrap w-full rounded-md border-0 p-2 pt-0 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 min-h-[40px]
          border-gray-300 bg-custom-white
          sm:text-sm sm:leading-6 px-2
          focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none
        `,
        className ?? "",
        disabled ? "cursor-not-allowed bg-gray-100" : ""
      )}>
      {value?.map((item: SelectOption, index: number) => (
        <Badge
          key={index}
          value={item}
          onDelete={handleDelete}
          className="mt-2"
          disabled={disabled}>
          {item.name}
        </Badge>
      ))}
    </div>
  );
});
