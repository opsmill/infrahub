import DateTimePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

import { Button } from "./button";
import { Input } from "./input";
import { forwardRef } from "react";

export const DatePicker = (props: any) => {
  const { date, onChange, onClickNow } = props;

  const CustomInput = forwardRef(
    ({ value, onClick }: any, ref) => (
      <Input onClick={onClick} ref={ref} value={value} className="rounded-r-none" />
    )
  );

  return (
    <div className="flex">
      <DateTimePicker
        dateFormat="yyyy/MM/dd HH:mm"
        selected={date}
        onChange={onChange}
        showTimeInput
        customInput={<CustomInput />}
        calendarStartDay={1}
      />

      <Button onClick={onClickNow} className="rounded-none rounded-r-md border-t border-r border-b border-gray-300">
        Now
      </Button>
    </div>
  );
};