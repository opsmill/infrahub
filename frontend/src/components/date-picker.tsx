import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { Button } from "./button";
import { Input } from "./input";
import { forwardRef, useRef, useState } from "react";
import { format, isValid } from "date-fns";

export const DatePicker = (props: any) => {
  const { date, onChange, onClickNow } = props;

  const [text, setText] = useState("");
  const [stateHasFocus, setStateHasFocus] = useState(false);
  const [hasError, setHasError] = useState({});

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
      setHasError({});
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

  const CustomInput = forwardRef(
    ({ onClick }: any, ref) => (
      <Input onClick={onClick} ref={ref} value={text} onChange={handleChangeInput} className="rounded-r-none" autoFocus={stateHasFocus} error={hasError} />
    )
  );

  return (
    <div className="flex">
      <DateTimePicker
        selected={date}
        onChange={handleChangeDate}
        showTimeInput
        customInput={<CustomInput ref={refCustomInput} />}
        calendarStartDay={1}
      />

      <Button onClick={handleClickNow} className="rounded-none rounded-r-md border-t border-r border-b border-gray-300" disabled={!date && !text}>
        Reset
      </Button>
    </div>
  );
};