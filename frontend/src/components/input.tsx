import React from "react";
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
export const Input = React.forwardRef((props: any, ref: any) => {
  const { className, onChange, error, ...propsToPass } = props;

  return (
    <div className="relative">
      <input
        type={props.type}
        onChange={(e) => onChange(e.target.value)}
        className={
          classNames(
            `
              block w-full rounded-md border-0 py-2 text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 placeholder:text-gray-400
            border-gray-300 bg-white
              sm:text-sm sm:leading-6 px-2
              focus:ring-2 focus:ring-inset focus:ring-indigo-600 focus:border-indigo-600 focus:outline-none
              disabled:cursor-not-allowed disabled:bg-gray-100
          `,
            className ?? "",
            error ? "ring-red-500 focus:ring-red-600" : ""
          )
        }
        {...propsToPass}
      />
      {
        error
        && error?.message
        && (
          <div className="absolute text-sm text-red-500 bg-white -bottom-2 ml-2 px-2">
            {error?.message}
          </div>
        )
      }
    </div>
  );
});
