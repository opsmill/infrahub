import { Icon } from "@iconify-icon/react";
import { formatISO, isEqual, isValid } from "date-fns";
import { useAtom } from "jotai";
import React, { useEffect } from "react";
import { StringParam, useQueryParam } from "use-query-params";
import BranchSelector from "../../components/branch-selector";
import { DatePicker } from "../../components/date-picker";
import { QSP } from "../../config/qsp";
import { debounce } from "../../utils/common";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { AccountMenu } from "../../components/AccountMenu";

interface Props {
  setSidebarOpen: React.Dispatch<React.SetStateAction<boolean>>;
}

export default function Header(props: Props) {
  const { setSidebarOpen } = props;

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
      <button
        type="button"
        className="border-r border-gray-200 p-4 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-custom-blue-500 md:hidden"
        onClick={() => setSidebarOpen(true)}>
        <span className="sr-only">Open sidebar</span>
        <Icon icon="mdi:menu" height="32" width="32" />
      </button>

      <div className="flex flex-1 items-center justify-end gap-4 pl-4">
        <DatePicker date={date} onChange={debouncedHandleDateChange} onClickNow={handleClickNow} />

        <BranchSelector />

        <AccountMenu />
      </div>
    </div>
  );
}
