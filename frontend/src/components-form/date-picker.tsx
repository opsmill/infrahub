import { classNames } from "../utils/common";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { DatePicker } from "../components/date-picker";

type OpsDatePickerProps = {
  label: string;
  value?: Date;
  onChange: (value?: Date) => void;
  className?: string;
  error?: FormFieldError;
}

export const OpsDatePicker = (props: OpsDatePickerProps) => {
  const { className, onChange, value, label, error } = props;

  return (
    <>
      <label
        className="block text-sm font-medium leading-6 text-gray-900">
        {label}
      </label>
      <DatePicker
        onChange={onChange}
        date={value}
        onClickNow={() => onChange()}
        className={classNames(className ?? "")}
        error={error}
      />
    </>
  );
};
