import { FormFieldError } from "../../screens/edit-form-hook/form";
import { SelectOption } from "../inputs/select";
import List from "../list";

type OpsListProps = {
  label: string;
  value: (string | SelectOption)[];
  onChange: (value: (string | SelectOption)[]) => void;
  error?: FormFieldError;
  isProtected?: boolean;
  disabled?: boolean;
};

export default function OpsList(props: OpsListProps) {
  return (
    <>
      <label className="block text-sm font-medium leading-6 text-gray-900" htmlFor={props.label}>
        {props.label}
      </label>
      <List {...props} disabled={props.isProtected || props.disabled} />
    </>
  );
}
