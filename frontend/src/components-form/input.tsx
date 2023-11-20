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

type InputTooltip = {
  label: string;
};

const InputUniqueTooltip = ({ label = "This field" }: InputTooltip) => (
  <Tooltip message={label + " must be unique"}>
    <Icon icon="mdi:key-outline" height="20" width="20" />
  </Tooltip>
);

const InputProtectedTooltip = ({ label = "This field" }: InputTooltip) => (
  <Tooltip message={label + " is protected"}>
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
        {isUnique && <InputUniqueTooltip label={label} />}
        {isProtected && <InputProtectedTooltip label={label} />}
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
