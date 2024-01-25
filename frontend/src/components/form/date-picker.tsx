import { LockClosedIcon } from "@heroicons/react/24/outline";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { classNames } from "../../utils/common";
import { DatePicker } from "../inputs/date-picker";

type OpsDatePickerProps = {
  label: string;
  value?: Date;
  onChange: (value?: Date) => void;
  className?: string;
  error?: FormFieldError;
  disabled?: boolean;
  isOptional?: boolean;
  isProtected?: boolean;
};

export const OpsDatePicker = (props: OpsDatePickerProps) => {
  const { className, onChange, value, label, error, isOptional, disabled, isProtected } = props;

  return (
    <>
      <label className="flex items-center">
        <div className="block text-sm font-medium leading-6 text-gray-900">
          {label} {isOptional ? "" : "*"}
        </div>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
      </label>
      <DatePicker
        onChange={onChange}
        date={value}
        onClickNow={() => onChange()}
        className={classNames(className ?? "")}
        error={error}
        disabled={!!disabled}
        isProtected={isProtected || disabled}
      />
    </>
  );
};
