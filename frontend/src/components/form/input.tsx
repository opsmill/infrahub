import { LockClosedIcon } from "@heroicons/react/24/outline";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { classNames } from "../../utils/common";
import { QuestionMark } from "../display/question-mark";
import { Input } from "../inputs/input";

type OpsInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  description?: string;
  error?: FormFieldError;
  type: string;
  isProtected?: boolean;
  isOptional?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
};

const InputUniqueTips = () => <span className="text-xs text-gray-600 italic">must be unique</span>;

export const OpsInput = (props: OpsInputProps) => {
  const {
    className,
    onChange,
    value,
    label,
    description,
    error,
    isProtected,
    isOptional,
    isUnique,
    disabled,
  } = props;

  return (
    <>
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
        {isUnique && <InputUniqueTips />}
        <QuestionMark message={description} />
      </div>
      <Input
        id={label}
        type={props.type}
        onChange={onChange}
        value={value}
        className={classNames(className ?? "")}
        error={error}
        disabled={isProtected || disabled}
      />
    </>
  );
};
