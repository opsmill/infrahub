import { forwardRef } from "react";
import { classNames } from "../utils/common";

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
  const { className, onChange, error, ...propsToPass } = props;

  return (
    <div className="relative">
      <input
        onChange={(event) => {
          const value =
            propsToPass.type === "number" ? event.target.valueAsNumber : event.target.value;

          onChange(value);
        }}
        className={classNames(
          `
                block w-full rounded-md border-0 py-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400
                border-gray-300 bg-custom-white
                sm:text-sm sm:leading-6 px-2
                focus:ring-2 focus:ring-inset focus:ring-custom-blue-600 focus:border-custom-blue-600 focus:outline-none
                disabled:cursor-not-allowed disabled:bg-gray-100
            `,
          className ?? "",
          error && error?.message ? "ring-red-500 focus:ring-red-600" : ""
        )}
        {...propsToPass}
      />
      {error?.message && (
        <div
          className="absolute text-sm text-red-500 bg-custom-white -bottom-2 ml-2 px-2"
          data-cy="field-error-message">
          {error?.message}
        </div>
      )}
    </div>
  );
});
