import { Icon } from "@iconify-icon/react";
import { forwardRef, useState } from "react";
import { classNames } from "../../utils/common";
import { BUTTON_TYPES, Button } from "../buttons/button";

// type InputProps = {
//   value?: string;
//   defaultValue?: string;
//   onChange: (value: string) => void;
//   className?: string;
//   error?: boolean;
//   disabled?: boolean;
//   error?: FormFieldError;
// }

// Forward ref used for Combobox.Input in Select
// eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
export const Input = forwardRef((props: any, ref: any) => {
  const { className, onChange, error, type, hideEmpty, ...propsToPass } = props;

  const [display, setDisplay] = useState(false);

  const handleInputChange = (event: any) => {
    const value = type === "number" ? event.target.valueAsNumber : event.target.value;

    onChange(value, event);
  };

  const displayButton = (
    <Button buttonType={BUTTON_TYPES.INVISIBLE} onClick={() => setDisplay(!display)}>
      <Icon icon={display ? "mdi:eye" : "mdi:eye-off"} className="text-gray-600" />
    </Button>
  );

  const removeButton = (
    <Button
      buttonType={BUTTON_TYPES.INVISIBLE}
      onClick={(event) => onChange(type === "number" ? 0 : "", event)}>
      <Icon icon="mdi:close" className="text-gray-400" />
    </Button>
  );

  return (
    <div className="relative flex items-center h-full w-full">
      <input
        onChange={handleInputChange}
        className={classNames(
          `block w-full rounded-md border-0 py-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400
          border-gray-300 bg-custom-white
          sm:text-sm sm:leading-6 px-2
          focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none
          disabled:cursor-not-allowed disabled:bg-gray-100`,
          className ?? "",
          error && error?.message ? "ring-red-500 focus:ring-red-600" : "",
          props.type === "password" ? "pr-14" : ""
        )}
        type={type === "password" && display ? "text" : type}
        {...propsToPass}
      />

      {propsToPass.value && !hideEmpty && (
        <div className="absolute right-2 top-0 bottom-0 flex items-center">{removeButton}</div>
      )}

      {error?.message && (
        <div
          className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2"
          data-cy="field-error-message">
          {error?.message}
        </div>
      )}

      {type === "password" && (
        <div className="absolute right-4 top-0 bottom-0 flex items-center">{displayButton}</div>
      )}
    </div>
  );
});
