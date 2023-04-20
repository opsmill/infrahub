import { Select } from "../components/select";

export type HasNameAndID = {
  id: string;
  name: string;
}

type SelectProps = {
  label: string;
  value: string | undefined;
  options: Array<HasNameAndID>;
  disabled: boolean;
  onChange: (value: HasNameAndID) => void;
}

export const OpsSelect = (props: SelectProps) => {
  return (
    <Select {...props} />
  );
};