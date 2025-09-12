import { Icon } from "@iconify-icon/react";
import { forwardRef, useState } from "react";

import { BUTTON_TYPES, Button } from "@/shared/components/buttons/button";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

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
      disabled={propsToPass?.disabled}
      buttonType={BUTTON_TYPES.INVISIBLE}
      onClick={(event) => onChange(type === "number" ? 0 : "", event)}
    >
      <Icon icon="mdi:close" className="text-gray-400" />
    </Button>
  );

  return (
    <div className="relative flex w-full items-center">
      <input
        onChange={handleInputChange}
        className={classNames(
          inputStyle,
          className,
          error && error?.message ? "ring-red-500 focus:ring-red-600" : "",
          props.type === "password" ? "pr-14" : ""
        )}
        type={type === "password" && display ? "text" : type}
        ref={ref}
        {...propsToPass}
      />

      {propsToPass.value && !hideEmpty && (
        <div
          className={classNames(
            "absolute top-0 bottom-0 flex items-center",
            type === "number" ? "right-4" : "right-1"
          )}
        >
          {removeButton}
        </div>
      )}

      {error?.message && (
        <div
          className="-bottom-2 absolute ml-2 bg-white px-2 text-red-500 text-sm"
          data-cy="field-error-message"
        >
          {error?.message}
        </div>
      )}

      {type === "password" && (
        <div className="absolute top-0 right-6 bottom-0 flex items-center">{displayButton}</div>
      )}
    </div>
  );
});
