import { classNames } from "../utils/common";
import { Input } from "../components/input";
import { FormFieldError } from "../screens/edit-form-hook/form";

type OpsInputProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
}

export const OpsInput = (props: OpsInputProps) => {
  const { className, onChange, value, label, error } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <Input
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(className ?? "")}
        error={error}
      />
    </>
  );
};
