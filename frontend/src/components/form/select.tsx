import { LockClosedIcon } from "@heroicons/react/24/outline";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { Select, SelectOption } from "../inputs/select";

type SelectProps = {
  label: string;
  value?: string | number | null;
  options?: Array<SelectOption>;
  onChange: (value: string | number) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  dropdown?: boolean;
  enum?: boolean;
  multiple?: boolean;
};

export const OpsSelect = (props: SelectProps) => {
  const { label, isProtected, isOptional, ...propsToPass } = props;

  const getLabel = () => {
    if (label && isOptional) {
      return label;
    }

    if (label && !isOptional) {
      return `${label} *`;
    }

    return "";
  };

  return (
    <>
      <div className="flex items-center">
        {label && (
          <>
            <label htmlFor={label} className="block text-sm font-medium leading-6 text-gray-900">
              {getLabel()}
            </label>
            <div className="ml-2">
              {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null}{" "}
            </div>
          </>
        )}
      </div>
      <Select {...propsToPass} disabled={isProtected} />
    </>
  );
};
