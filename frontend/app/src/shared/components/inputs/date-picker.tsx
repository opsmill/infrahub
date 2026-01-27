import { Icon } from "@iconify-icon/react";
import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { format, isValid } from "date-fns";
import { forwardRef, useEffect, useRef, useState } from "react";

import { BUTTON_TYPES, Button } from "@/shared/components/buttons/button";
import { inputStyle } from "@/shared/components/ui/style";
import { classNames } from "@/shared/utils/common";

const DEFAULT_DATE_FORMAT = "MM/dd/yyyy HH:mm";

export const DatePicker = forwardRef<HTMLInputElement, any>((props, ref) => {
  const { id, date, onChange, disabled, isProtected, className } = props;

  const currentDate = date && isValid(date) ? date : null;

  const [text, setText] = useState(currentDate ? format(currentDate, DEFAULT_DATE_FORMAT) : "");
  const refCustomInput = useRef(ref);

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

  const CustomInput = forwardRef(({ onClick }: any, ref: any) => (
    <div className="relative flex w-full items-center">
      <input
        id={id}
        onClick={onClick}
        ref={ref}
        value={text}
        onChange={handleChangeInput}
        className={classNames(inputStyle, className)}
        disabled={isDisabled}
      />

      {text && !isDisabled && (
        <div className="absolute top-0 right-1 bottom-0 flex items-center">
          <Button
            buttonType={BUTTON_TYPES.INVISIBLE}
            onClick={(e) => {
              e.stopPropagation();
              handleClear();
            }}
          >
            <Icon icon="mdi:close" className="text-gray-400" />
          </Button>
        </div>
      )}
    </div>
  ));

  return (
    <div className="w-full" data-testid="date-picker">
      <DateTimePicker
        selected={currentDate}
        onChange={handleChangeDate}
        customInput={<CustomInput ref={refCustomInput} />}
        wrapperClassName="w-full"
        showTimeSelect
        timeIntervals={1}
        calendarStartDay={1}
      />
    </div>
  );
});
