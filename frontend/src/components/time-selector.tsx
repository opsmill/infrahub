import { Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { format, setHours, setMinutes } from "date-fns";
import { useAtom } from "jotai/index";
import { HTMLAttributes, forwardRef, useEffect } from "react";
import DateTimePicker from "react-datepicker";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";
import { datetimeAtom } from "../state/atoms/time.atom";
import { classNames } from "../utils/common";
import { Button } from "./buttons/button-primitive";

export const TimeFrameSelector = () => {
  const [date, setDate] = useAtom(datetimeAtom);
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, DateTimeParam);

  useEffect(() => {
    if (date === qspDate) return;
    setDate(qspDate ?? null);
  }, [qspDate]);

  const onChange = (newDate: Date) => {
    setDate(newDate);
    setQspDate(newDate);
  };

  const reset = () => {
    setDate(null);
    setQspDate(undefined);
  };

  return (
    <div
      className={classNames(
        "inline-flex bg-custom-blue-800 text-white rounded-full",
        date && "bg-orange-600 shadow-md"
      )}
      data-testid="timeframe-selector">
      <Transition
        show={!!date}
        enter="linear duration-300"
        enterFrom="w-0 opacity-0"
        enterTo="w-[174px] opacity-100"
        leave="linear duration-300"
        leaveFrom="w-[174px] opacity-100"
        leaveTo="w-0 opacity-0"
        className="flex items-center">
        <ButtonStyled onClick={reset} data-testid="reset-timeframe-selector">
          <Icon icon="mdi:close" />
        </ButtonStyled>

        <div className="w-[136px] flex flex-col truncate">
          <span className="font-medium text-xs">Current view time:</span>
          {date && <span className="text-sm">{format(date, "PP | H:mm")}</span>}
        </div>
      </Transition>

      <DateTimePicker
        customInput={
          <ButtonStyled>
            <Icon icon="mdi:calendar-clock" className="text-2xl" />
          </ButtonStyled>
        }
        selected={date}
        onChange={onChange}
        showTimeSelect
        timeIntervals={10}
        calendarStartDay={1}
        maxDate={new Date()}
        minTime={setHours(setMinutes(new Date(), 0), 0)}
        maxTime={new Date()}
      />
    </div>
  );
};

const ButtonStyled = forwardRef<HTMLButtonElement, HTMLAttributes<HTMLButtonElement>>(
  ({ className, ...props }, ref) => (
    <Button
      ref={ref}
      size="icon"
      variant="ghost"
      className={classNames("p-3 h-auto w-auto hover:bg-gray-100/20", className)}
      {...props}
    />
  )
);
