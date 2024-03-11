import { useAtom } from "jotai/index";
import { datetimeAtom } from "../state/atoms/time.atom";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";
import { Icon } from "@iconify-icon/react";
import DateTimePicker from "react-datepicker";
import { classNames } from "../utils/common";
import { format, setHours, setMinutes } from "date-fns";
import { forwardRef, HTMLAttributes, useEffect } from "react";
import { Transition } from "@headlessui/react";

export const TimeFrameSelector = () => {
  const [date, setDate] = useAtom(datetimeAtom);
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, DateTimeParam);

  useEffect(() => {
    if (date) return;
    if (!qspDate) return;

    setDate(qspDate);
  }, []);

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
        "inline-flex bg-gray-800 text-white rounded-full",
        date && "bg-orange-600 shadow-md"
      )}
      data-testid="timeframe-selector">
      <Transition
        show={!!date}
        enter="ease-out duration-300"
        enterFrom="w-0"
        enterTo="w-40"
        leave="ease-out duration-300"
        leaveFrom="w-40"
        leaveTo="w-0"
        className="flex items-center truncate">
        <ButtonStyled onClick={reset} data-testid="reset-timeframe-selector">
          <Icon icon="mdi:close" />
        </ButtonStyled>

        <div className="flex flex-col">
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
    <button
      ref={ref}
      className={classNames(
        "inline-flex p-3 rounded-full focus:outline-none focus:ring-2 focus:ring-custom-blue-500 focus:ring-offset-2",
        className
      )}
      {...props}
    />
  )
);
