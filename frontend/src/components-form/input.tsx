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
  isOptional?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
};

const InputUniqueTips = () => <span className="text-xs text-gray-600 italic">must be unique</span>;

export const OpsInput = (props: OpsInputProps) => {
  const { className, onChange, value, label, error, isProtected, isOptional, isUnique, disabled } =
    props;

  return (
    <>
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
        {isUnique && <InputUniqueTips />}
      </div>
      <Input
        id={label}
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
