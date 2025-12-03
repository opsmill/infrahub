import { Transition } from "@headlessui/react";
import { Icon } from "@iconify-icon/react";
import { format, isPast } from "date-fns";
import { useAtom } from "jotai";
import { parseAsIsoDateTime, useQueryState } from "nuqs";
import React from "react";
import DateTimePicker from "react-datepicker";

import { QSP } from "@/shared/config/qsp";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { classNames } from "@/shared/utils/common";

import { Button } from "./buttons/button-primitive";

import "react-datepicker/dist/react-datepicker.css";

export const TimeFrameSelector = () => {
  const [qspDate, setQspDate] = useQueryState(QSP.DATETIME, parseAsIsoDateTime);
  const [date, setDate] = useAtom(datetimeAtom);

  React.useEffect(() => {
    if (date === qspDate) return;
    setDate(qspDate ?? null);
  }, []);

  const onChange = (newDate: Date | null) => {
    setDate(newDate);
    setQspDate(newDate);
  };

  const reset = () => {
    setDate(null);
    setQspDate(null);
  };

  return (
    <div
      className={classNames(
        "inline-flex h-8 items-center overflow-hidden rounded-lg border border-neutral-200 dark:border-slate-600",
        date && "bg-neutral-800 dark:bg-slate-700"
      )}
    >
      <DateTimePicker
        customInput={
          <Button
            size="square"
            variant="ghost"
            className="h-8 w-8 bg-neutral-50 dark:bg-slate-700"
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
        popperPlacement="bottom-start"
        popperClassName="z-50!"
      />

      <Transition
        as="div"
        show={!!date}
        enter="linear duration-300"
        enterFrom="w-0 opacity-0"
        enterTo="w-[158px] opacity-100"
        leave="linear duration-300"
        leaveFrom="w-[158px] bg-red-200 h-full w-full opacity-100"
        leaveTo="w-0 opacity-0"
        className="inline-flex items-center text-white text-xxs"
      >
        <Icon icon="mdi:history" className="m-1.5 text-xl" />

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
