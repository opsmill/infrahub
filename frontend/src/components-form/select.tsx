import { LockClosedIcon } from "@heroicons/react/24/outline";
import { Select, SelectOption } from "../components/select";
import { FormFieldError } from "../screens/edit-form-hook/form";

type SelectProps = {
  label: string;
  value?: string | number;
  options: Array<SelectOption>;
  disabled: boolean;
  onChange: (value: SelectOption) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptionnal?: boolean;
};

export const OpsSelect = (props: SelectProps) => {
  const { label, isProtected, isOptionnal, ...propsToPass } = props;

  const getLabel = () => {
    if (label && isOptionnal) {
      return label;
    }

    if (label && !isOptionnal) {
      return `${label} *`;
    }

    return "";
  };

  return (
    <>
      <div className="flex items-center">
        <label className="block text-sm font-medium leading-6 text-gray-900">{getLabel()}</label>
        <div className="ml-2"> {isProtected ? <LockClosedIcon className="w-4 h-4" /> : null} </div>
      </div>
      <Select {...propsToPass} disabled={isProtected} />
    </>
  );
};
