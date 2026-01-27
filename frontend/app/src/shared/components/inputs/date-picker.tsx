import { Icon } from "@iconify-icon/react";
import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { format, isValid } from "date-fns";
import { forwardRef, useEffect, useState } from "react";

import { Button } from "@/shared/components/buttons/button-primitive";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

const DEFAULT_DATE_FORMAT = "MM/dd/yyyy HH:mm";

interface CustomInputProps {
  id?: string;
  value: string;
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  onChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onClear: () => void;
}

const CustomInput = forwardRef<HTMLInputElement, CustomInputProps>(
  ({ id, value, disabled, className, onClick, onChange, onClear }, ref) => (
    <div className="relative flex w-full items-center">
      <input
        id={id}
        onClick={onClick}
        ref={ref}
        value={value}
        onChange={onChange}
        className={classNames(inputStyle, className)}
        disabled={disabled}
      />

      {value && !disabled && (
        <div className="absolute top-0 right-1 bottom-0 flex items-center">
          <Button
            variant="ghost"
            size="icon"
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
          >
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        </div>
      )}
    </div>
  )
);

export const DatePicker = forwardRef<HTMLInputElement, any>((props, _ref) => {
  const { id, date, onChange, disabled, isProtected, className } = props;

  const currentDate = date && isValid(date) ? date : null;

  const [text, setText] = useState(currentDate ? format(currentDate, DEFAULT_DATE_FORMAT) : "");

  const handleChangeDate = (newDate: Date | null) => {
    if (newDate) {
      setText(format(newDate, DEFAULT_DATE_FORMAT));
      onChange(newDate);
    }
  };

  const handleChangeInput = (event: React.ChangeEvent<HTMLInputElement>) => {
    const value = event.target.value;
    setText(value);

    if (!value) {
      onChange();
    }

    if (value && isValid(new Date(value))) {
      onChange(new Date(value));
    }
  };

  const handleClear = () => {
    setText("");
    onChange();
  };

  useEffect(() => {
    if (currentDate) {
      setText(format(currentDate, DEFAULT_DATE_FORMAT));
    }
  }, [currentDate]);

  const isDisabled = disabled || isProtected;

  return (
    <div className="w-full" data-testid="date-picker">
      <DateTimePicker
        selected={currentDate}
        onChange={handleChangeDate}
        customInput={
          <CustomInput
            id={id}
            value={text}
            disabled={isDisabled}
            className={className}
            onChange={handleChangeInput}
            onClear={handleClear}
          />
        }
        wrapperClassName="w-full"
        showTimeSelect
        timeIntervals={1}
        calendarStartDay={1}
        dateFormat={DEFAULT_DATE_FORMAT}
      />
    </div>
  );
});
