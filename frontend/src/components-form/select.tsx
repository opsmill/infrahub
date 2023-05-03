import { Select, SelectOption } from "../components/select";
import { FormFieldError } from "../screens/edit-form-hook/form";

type SelectProps = {
  label: string;
  value?: string;
  options: Array<SelectOption>;
  disabled: boolean;
  onChange: (value: SelectOption) => void;
  error?: FormFieldError;
}

export const OpsSelect = (props: SelectProps) => {
  const { label, ...propsToPass } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <Select {...propsToPass} />
    </>
  );
};