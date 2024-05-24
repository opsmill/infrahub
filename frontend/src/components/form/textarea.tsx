import { LockClosedIcon } from "@heroicons/react/24/outline";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { classNames } from "../../utils/common";
import { QuestionMark } from "../display/question-mark";
import { TextareaWithEditor } from "../inputs/textarea-with-editor";

type OpsInputProps = {
  label: string;
  placeholder?: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  description?: string;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  disabled?: boolean;
};

export const OpsTextarea = (props: OpsInputProps) => {
  const {
    className,
    onChange,
    placeholder,
    value,
    label,
    description,
    error,
    isProtected,
    isOptional,
    disabled,
  } = props;

  return (
    <>
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
        <QuestionMark message={description} />
      </div>

      <TextareaWithEditor
        onChange={onChange}
        defaultValue={value ?? ""}
        placeholder={placeholder}
        className={classNames(className ?? "")}
        error={error}
        disabled={isProtected || disabled}
      />
    </>
  );
};
