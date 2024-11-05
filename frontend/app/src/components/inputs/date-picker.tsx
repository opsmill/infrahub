import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { Button } from "@/components/buttons/button";
import { Input } from "@/components/inputs/input";
import { format, isValid } from "date-fns";
import { forwardRef, useEffect, useRef, useState } from "react";

export const DatePicker = forwardRef<HTMLInputElement, any>((props, ref) => {
  const { id, date, onChange, disabled, isProtected } = props;

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
      className="rounded-r-none"
      disabled={disabled || isProtected}
    />
  ));

  return (
    <div className="flex" data-testid="date-picker">
      <DateTimePicker
        selected={currentDate}
        onChange={handleChangeDate}
        showTimeInput
        customInput={<CustomInput ref={refCustomInput} />}
        calendarStartDay={1}
      />

      <Button
        onClick={handleClickNow}
        className="rounded-none rounded-r-md border-t border-r border-b border-gray-300"
        disabled={disabled || isProtected || (!currentDate && !text)}
      >
        Reset
      </Button>
    </div>
  );
});
