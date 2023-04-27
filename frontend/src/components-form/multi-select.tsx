import { MultiSelect } from "../components/multi-select";
import { SelectOption } from "../components/select";
import { FormFieldError } from "../screens/edit-form-hook/form";

type OpsMultiSelectProps = {
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  onChange: (value: SelectOption[]) => void;
  error?: FormFieldError;
}

export default function OpsMultiSelect(props: OpsMultiSelectProps) {
  const { value, options, onChange, label, error } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <MultiSelect
        value={value}
        options={options}
        onChange={onChange}
        error={error}
      />
    </>
  );
}
