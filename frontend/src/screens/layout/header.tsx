import { formatISO, isEqual, isValid } from "date-fns";
import { useAtom } from "jotai";
import React, { useEffect } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import { AccountMenu } from "../../components/account-menu";
import BranchSelector from "../../components/branch-selector";
import { DatePicker } from "../../components/inputs/date-picker";
import { QSP } from "../../config/qsp";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { debounce } from "../../utils/common";
import { SearchBar } from "./search-bar";

export default function Header() {
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, StringParam);
  const [date, setDate] = useAtom(datetimeAtom);

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
    <div className="z-10 flex justify-between flex-shrink-0 h-16 bg-custom-white shadow pr-4">
      <SearchBar />

      <div className="flex items-center justify-end gap-4 pl-4">
        <DatePicker date={date} onChange={debouncedHandleDateChange} onClickNow={handleClickNow} />

        <BranchSelector />

        <AccountMenu />
      </div>
    </div>
  );
}
