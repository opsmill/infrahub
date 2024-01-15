import { LockClosedIcon } from "@heroicons/react/24/outline";
import { useState } from "react";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { Checkbox } from "../inputs/checkbox";

interface Props {
  label: string;
  value: boolean;
  onChange: (value: boolean) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
}

export default function OpsCheckbox(props: Props) {
  const { label, onChange, value, error, isProtected, isOptional } = props;
  const [enabled, setEnabled] = useState(value);

  return (
    <div className="flex flex-col relative">
      <div className="flex items-center">
        <label htmlFor={label} className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
      </div>
      <div className="relative flex items-center">
        <Checkbox
          id={label}
          enabled={enabled}
          onChange={() => {
            onChange(!enabled);
            setEnabled(!enabled);
          }}
          disabled={isProtected}
        />
        {error?.message && (
          <div className="absolute text-sm text-red-500 ml-4 pl-2" data-cy="field-error-message">
            {error?.message}
          </div>
        )}
      </div>
    </div>
  );
}
