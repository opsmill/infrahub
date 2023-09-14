import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Input } from "../components/input";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";

type OpsInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
  type: string;
  isProtected?: boolean;
  isOptionnal?: boolean;
  disabled?: boolean;
};

export const OpsInput = (props: OpsInputProps) => {
  const { className, onChange, value, label, error, isProtected, isOptionnal, disabled } = props;

  return (
    <>
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptionnal ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
      </div>
      <Input
        type={props.type}
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(className ?? "")}
        error={error}
        disabled={isProtected || disabled}
      />
    </>
  );
};
