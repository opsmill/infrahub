import { Input } from "../components/input";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";
import { Icon } from "@iconify-icon/react";
import { Tooltip } from "../components/tooltip";

type OpsInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
  type: string;
  isProtected?: boolean;
  isOptionnal?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
};

const InputUniqueTips = () => <span className="text-xs text-gray-600 italic">must be unique</span>;

const InputProtectedTooltip = () => (
  <Tooltip message="you are not allowed to update this field">
    <Icon icon="mdi:lock-outline" height="20" width="20" />
  </Tooltip>
);

export const OpsInput = (props: OpsInputProps) => {
  const { className, onChange, value, label, error, isProtected, isOptionnal, isUnique, disabled } =
    props;

  return (
    <>
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptionnal && "*"}
        </label>
        {isProtected && <InputProtectedTooltip />}
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
