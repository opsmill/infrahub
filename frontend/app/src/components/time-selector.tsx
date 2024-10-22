import { QSP } from "@/config/qsp";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { format, isPast } from "date-fns";
import { useAtom } from "jotai/index";
import { useEffect } from "react";
import DateTimePicker from "react-datepicker";
import { DateTimeParam, useQueryParam } from "use-query-params";
import { Button } from "./buttons/button-primitive";

import "react-datepicker/dist/react-datepicker.css";

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
        "inline-flex items-center h-8 border border-neutral-200 rounded-lg overflow-hidden",
        date && "bg-neutral-800"
      )}
    >
      <DateTimePicker
        customInput={
          <Button
            size="square"
            variant="ghost"
            className="h-8 w-8 bg-neutral-50"
            data-testid="timeframe-selector"
          >
            <Icon icon="mdi:calendar-clock" className="text-xl" />
          </Button>
        }
        className="h-8 w-8"
        selected={date}
        onChange={onChange}
        showTimeSelect
        timeIntervals={1}
        calendarStartDay={1}
        maxDate={new Date()}
        filterTime={(date) => isPast(date)}
      />

      <Transition
        show={!!date}
        enter="linear duration-300"
        enterFrom="w-0 opacity-0"
        enterTo="w-[158px] opacity-100"
        leave="linear duration-300"
        leaveFrom="w-[158px] bg-red-200 h-full w-full opacity-100"
        leaveTo="w-0 opacity-0"
        className="inline-flex items-center text-white text-xxs"
      >
        <Icon icon="mdi:history" className="text-xl m-1.5" />

        <div className="flex flex-col items-center truncate">
          <span className="font-medium">Current view time</span>
          {date && <span>{format(date, "PP | H:mm")}</span>}
        </div>

        <Button
          size="square"
          variant="ghost"
          type="button"
          onClick={reset}
          className="h-8 w-8 hover:bg-neutral-700"
          data-testid="reset-timeframe-selector"
        >
          <Icon icon="mdi:close" />
        </Button>
      </Transition>
    </div>
  );
};
