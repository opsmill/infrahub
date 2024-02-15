import { DatePicker } from "./inputs/date-picker";
import { useAtom } from "jotai/index";
import { datetimeAtom } from "../state/atoms/time.atom";
import { useEffect } from "react";
import { formatISO, isEqual, isValid } from "date-fns";
import { debounce } from "../utils/common";
import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../config/qsp";

export const TimeFrameSelector = () => {
  const [date, setDate] = useAtom(datetimeAtom);
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, StringParam);

  useEffect(() => {
    // Remove the date from the state
    if (!qspDate || (qspDate && !isValid(new Date(qspDate)))) {
      setDate(null);
    }

    if (qspDate) {
      const newQspDate = new Date(qspDate);

      // Store the new QSP date only if it's not defined OR if it's different
      if (!date || (date && !isEqual(newQspDate, date))) {
        setDate(newQspDate);
      }
    }
  }, [date, qspDate]);

  const handleDateChange = (newDate: any) => {
    if (newDate) {
      setQspDate(formatISO(newDate));
    } else {
      // Undefined is needed to remove a parameter from the QSP
      setQspDate(undefined);
    }
  };
  const debouncedHandleDateChange = debounce(handleDateChange);

  const handleClickNow = () => {
    // Undefined is needed to remove a parameter from the QSP
    setQspDate(undefined);
  };

  return (
    <DatePicker date={date} onChange={debouncedHandleDateChange} onClickNow={handleClickNow} />
  );
};
