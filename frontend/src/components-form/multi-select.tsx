import { Select, SelectOption } from "../components/inputs/select";
import { FormFieldError } from "../screens/edit-form-hook/form";

type OpsMultiSelectProps = {
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  onChange: (value: SelectOption[]) => void;
  error?: FormFieldError;
  isProtected?: boolean;
};

export default function OpsMultiSelect(props: OpsMultiSelectProps) {
  const { value, options, onChange, label, error, isProtected, ...propsToPass } = props;

  return (
    <>
      <label className="block text-sm font-medium leading-6 text-gray-900">{label}</label>
      <Select
        {...propsToPass}
        value={value}
        options={options}
        onChange={onChange}
        error={error}
        disabled={isProtected}
        multiple
      />
    </>
  );
}
