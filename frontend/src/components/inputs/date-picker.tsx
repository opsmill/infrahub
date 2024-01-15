import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { format, isValid } from "date-fns";
import { forwardRef, useEffect, useRef, useState } from "react";
import { Button } from "../buttons/button";
import { Input } from "./input";

export const DatePicker = (props: any) => {
  const { date, onChange, onClickNow, error } = props;

  const currentDate = date && isValid(date) ? date : null;

  const [text, setText] = useState(currentDate ? format(currentDate, "MM/dd/yyy HH:mm") : "");
  const [stateHasFocus, setStateHasFocus] = useState(false);
  const [hasError, setHasError] = useState(error);

  const refCustomInput = useRef();

  const handleChangeDate = (newDate: Date) => {
    setStateHasFocus(true);
    setText(format(newDate, "MM/dd/yyy HH:mm"));
    onChange(newDate);
  };

  const handleChangeInput = (value: string) => {
    setStateHasFocus(true);
    setText(value);

    if (!value) {
      setHasError({ message: "Required" });
      onClickNow();
    }

    if (value && !isValid(new Date(value))) {
      setHasError({ message: "Not a valid date" });
    }

    if (value && isValid(new Date(value))) {
      setHasError({});
      onChange(new Date(value));
    }
  };

  const handleClickNow = () => {
    setText("");
    onClickNow();
    setStateHasFocus(false);
    setHasError({});
  };

  useEffect(() => {
    if (currentDate) {
      setText(format(currentDate, "MM/dd/yyy HH:mm"));
    }
  }, [currentDate]);

  const CustomInput = forwardRef(({ onClick }: any, ref: any) => (
    <Input
      onClick={onClick}
      ref={ref}
      value={text}
      onChange={handleChangeInput}
      className="rounded-r-none"
      autoFocus={stateHasFocus}
      error={hasError}
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
        disabled={!currentDate && !text}>
        Reset
      </Button>
    </div>
  );
};
