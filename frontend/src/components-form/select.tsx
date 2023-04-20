import { Select, SelectOption } from "../components/select";

type SelectProps = {
  label: string;
  value?: string;
  options: Array<SelectOption>;
  disabled: boolean;
  onChange: (value: SelectOption) => void;
}

export const OpsSelect = (props: SelectProps) => {
  const { label, value, ...propsToPass } = props;
  return (
    <Select {...propsToPass} />
  );
};