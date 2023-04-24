import { MultiSelect } from "../components/multi-select";
import { SelectOption } from "../components/select";

type OpsMultiSelectProps = {
  label: string;
  value: SelectOption[];
  options: SelectOption[];
  onChange: (value: SelectOption[]) => void;
}

export default function OpsMultiSelect(props: OpsMultiSelectProps) {
  const { value, options, onChange, label } = props;

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
      />
    </>
  );
}
