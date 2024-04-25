import { FormFieldError } from "../../screens/edit-form-hook/form";
import { Select, SelectOption } from "../inputs/select";

type OpsMultiSelectProps = {
  label: string;
  value: SelectOption[];
  options?: SelectOption[];
  onChange: (value: SelectOption[]) => void;
  error?: FormFieldError;
  isProtected?: boolean;
};

export default function OpsMultiSelect(props: OpsMultiSelectProps) {
  const { label, isProtected, ...propsToPass } = props;

  return (
    <>
      <label className="block text-sm font-medium leading-6 text-gray-900">{label}</label>
      <Select {...propsToPass} disabled={isProtected} multiple />
    </>
  );
}
