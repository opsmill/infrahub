import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { format, isValid } from "date-fns";
import { forwardRef, useEffect, useRef, useState } from "react";

import { Button } from "@/shared/components/buttons/button";
import { Input } from "@/shared/components/inputs/input";
import { classNames } from "@/shared/utils/common";

export const DatePicker = forwardRef<HTMLInputElement, any>((props, ref) => {
  const { id, date, onChange, disabled, isProtected, className } = props;

  const currentDate = date && isValid(date) ? date : null;

  const [text, setText] = useState(currentDate ? format(currentDate, "MM/dd/yyy HH:mm") : "");
  const refCustomInput = useRef(ref);

  const handleChangeDate = (newDate: Date) => {
    setText(format(newDate, "MM/dd/yyy HH:mm"));
    onChange(newDate);
  };

  const handleChangeInput = (value: string) => {
    setText(value);

    if (!value) {
      onChange();
    }

    if (value && isValid(new Date(value))) {
      onChange(new Date(value));
    }
  };

  const handleClickNow = () => {
    setText("");
    onChange();
  };

  useEffect(() => {
    if (currentDate) {
      setText(format(currentDate, "MM/dd/yyy HH:mm"));
    }
  }, [currentDate]);

  const CustomInput = forwardRef(({ onClick }: any, ref: any) => (
    <Input
      id={id}
      onClick={onClick}
      ref={ref}
      value={text}
      onChange={handleChangeInput}
      className={classNames("rounded-r-none", className)}
      disabled={disabled || isProtected}
    />
  ));

  return (
    <div className="flex" data-testid="date-picker">
      <DateTimePicker
        selected={currentDate}
        onChange={handleChangeDate}
        customInput={<CustomInput ref={refCustomInput} />}
        showTimeSelect
        timeIntervals={1}
        calendarStartDay={1}
      />

      <Button
        onClick={handleClickNow}
        className="rounded-none rounded-r-md border-gray-300 border-t border-r border-b"
        disabled={disabled || isProtected || (!currentDate && !text)}
      >
        Reset
      </Button>
    </div>
  );
});
