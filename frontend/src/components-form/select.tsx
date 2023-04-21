import { Select, SelectOption } from "../components/select";

type SelectProps = {
  label: string;
  value?: string;
  options: Array<SelectOption>;
  disabled: boolean;
  onChange: (value: SelectOption) => void;
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