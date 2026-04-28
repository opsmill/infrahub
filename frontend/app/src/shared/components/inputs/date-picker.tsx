import { Icon } from "@iconify-icon/react";
import type React from "react";
import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { isValid } from "date-fns";

import { Button } from "@/shared/components/aria/button";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";
import { DATE_TIME_FORMAT } from "@/shared/utils/date";

interface CustomInputProps {
  id?: string;
  value?: string;
  disabled?: boolean;
  className?: string;
  onClick?: () => void;
  ref?: React.Ref<HTMLInputElement>;
}

const CustomInput = ({ id, value, disabled, className, onClick, ref }: CustomInputProps) => (
  <input
    id={id}
    onClick={onClick}
    ref={ref}
    value={value}
    readOnly
    className={classNames(inputStyle, "cursor-pointer pr-10", className)}
    disabled={disabled}
  />
);

interface DatePickerProps {
  id?: string;
  date?: Date | null;
  onChange: (date: Date | null) => void;
  disabled?: boolean;
  isProtected?: boolean;
  className?: string;
}

export const DatePicker = ({
  id,
  date,
  onChange,
  disabled,
  isProtected,
  className,
}: DatePickerProps) => {
  const currentDate = date && isValid(date) ? date : null;

  const handleChangeDate = (newDate: Date | null) => {
    if (newDate) {
      onChange(newDate);
    }
  };

  const handleClear = () => {
    onChange(null);
  };

  const isDisabled = disabled || isProtected;

  return (
    <div className="relative w-full" data-testid="date-picker">
      <DateTimePicker
        selected={currentDate}
        onChange={handleChangeDate}
        customInput={<CustomInput id={id} disabled={isDisabled} className={className} />}
        wrapperClassName="w-full"
        calendarClassName="flex!"
        showTimeSelect
        timeIntervals={1}
        calendarStartDay={1}
        dateFormat={DATE_TIME_FORMAT}
      />

      {currentDate && !isDisabled && (
        <div className="absolute top-0 right-1 bottom-0 flex items-center">
          <Button
            variant="ghost"
            size="xs"
            shape="circle"
            onPress={() => {
              handleClear();
            }}
          >
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        </div>
      )}
    </div>
  );
};
