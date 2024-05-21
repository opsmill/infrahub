import React from "react";
import { classNames } from "../../utils/common";
import { Badge } from "../display/badge";
import { ErrorMessage } from "./constants";
import { SelectOption } from "./select";

type MultipleInputProps = {
  value: (string | SelectOption)[];
  onChange: (items: (string | SelectOption)[]) => void;
  className?: string;
  disabled?: boolean;
  error?: ErrorMessage;
};

// Forward ref used for Combobox.Input in Select
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
export const MultipleInput = React.forwardRef((props: MultipleInputProps, ref: any) => {
  const { className, onChange, value, disabled, error } = props;

  // Remove item from list
  const handleDelete = (item: string | SelectOption) => {
    const newValues = value?.filter((v: string | SelectOption) => {
      if (typeof v === "string" && typeof item === "string") {
        return v !== item;
      }

      if (typeof v === "object" && typeof item === "object") {
        return v.id !== item.id;
      }
    });

    return onChange(newValues);
  };

  if (!value?.length) {
    return (
      <>
        <div
          className={classNames(
            `flex items-center justify-center flex-wrap w-full rounded-md border-0 shadow-sm ring-1 ring-inset ring-gray-300 min-h-[44px]
          border-gray-300 bg-custom-white
          sm:text-sm sm:leading-6 px-2
          text-gray-400 italic
          `,
            className ?? "",
            disabled ? "cursor-not-allowed bg-gray-100" : "",
            error && error?.message ? "ring-red-500 focus:ring-red-600" : ""
          )}
          data-testid="multi-select-input">
          Empty list
        </div>

        {error?.message && (
          <div
            className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2 text-left"
            data-cy="field-error-message">
            {error?.message}
          </div>
        )}
      </>
    );
  }

  return (
    <div
      className={classNames(
        `flex flex-wrap w-full rounded-md border-0 p-2 pt-0 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400 min-h-[44px]
          border-gray-300 bg-custom-white
          sm:text-sm sm:leading-6 px-2
          focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none
        `,
        className ?? "",
        disabled ? "cursor-not-allowed bg-gray-100" : ""
      )}
      data-testid="multi-select-input">
      {value?.map((item: string | SelectOption, index: number) => (
        <Badge
          key={index}
          value={item}
          onDelete={handleDelete}
          className="mt-2"
          data-testid="multi-select-input-badge"
          disabled={disabled}>
          {typeof item === "object" ? item.name : item}
        </Badge>
      ))}
    </div>
  );
});
