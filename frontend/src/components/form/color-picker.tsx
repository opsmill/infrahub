import { QuestionMark } from "@/components/display/question-mark";
import { FormFieldError } from "@/screens/edit-form-hook/form";
import { classNames } from "@/utils/common";
import { LockClosedIcon } from "@heroicons/react/24/outline";
import { components } from "../../infraops";
import { ColorPicker } from "../inputs/color-picker";

type OpsColorPickerProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
  field:
    | components["schemas"]["AttributeSchema-Output"]
    | components["schemas"]["RelationshipSchema-Output"];
};

export const OpsColorPicker = (props: OpsColorPickerProps) => {
  const { className, onChange, value, label, error, isProtected, isOptional, disabled, field } =
    props;

  return (
    <>
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
        <QuestionMark message={field?.description} />
      </div>
      <ColorPicker
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(className ?? "")}
        error={error}
        disabled={isProtected || disabled}
      />
    </>
  );
};
