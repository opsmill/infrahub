import { DatePicker } from "../components/date-picker";
import { FormFieldError } from "../screens/edit-form-hook/form";
import { classNames } from "../utils/common";

type OpsDatePickerProps = {
  label: string;
  value?: Date;
  onChange: (value?: Date) => void;
  className?: string;
  error?: FormFieldError;
  isOptionnal?: boolean;
};

export const OpsDatePicker = (props: OpsDatePickerProps) => {
  const { className, onChange, value, label, error, isOptionnal } = props;

  return (
    <>
      <label className="block text-sm font-medium leading-6 text-gray-900">
        {label} {isOptionnal ? "" : "*"}
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
