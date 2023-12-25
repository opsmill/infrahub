import { MagnifyingGlassIcon } from "@heroicons/react/20/solid";
import { Bars3BottomLeftIcon } from "@heroicons/react/24/outline";
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
    <div className="z-10 flex h-16 flex-shrink-0 bg-custom-white shadow">
      <button
        type="button"
        className="border-r border-gray-200 px-4 text-gray-500 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-custom-blue-500 md:hidden"
        onClick={() => setSidebarOpen(true)}>
        <span className="sr-only">Open sidebar</span>
        <Bars3BottomLeftIcon className="h-6 w-6" aria-hidden="true" />
      </button>

      <div className="flex flex-1 justify-between px-4">
        <div className="flex flex-1 opacity-30">
          <form className="flex w-full md:ml-0" action="#" method="GET">
            <label htmlFor="search-field" className="sr-only">
              Search
            </label>
            <div className="relative w-full text-gray-400 focus-within:text-gray-600">
              <div className="pointer-events-none absolute inset-y-0 left-0 flex items-center">
                <MagnifyingGlassIcon className="w-4 h-4" aria-hidden="true" />
              </div>
              <input
                onChange={() => {}}
                id="search-field"
                className="block h-full w-full border-transparent py-2 pl-8 pr-3 text-gray-900 placeholder-gray-500 focus:border-transparent focus:placeholder-gray-400 focus:outline-none focus:ring-0 sm:text-sm cursor-not-allowed"
                placeholder="Search"
                type="search"
                name="search"
              />
            </div>
          </form>
        </div>

        <div className="flex items-center gap-4 ml-4 md:ml-6">
          <DatePicker
            date={date}
            onChange={debouncedHandleDateChange}
            onClickNow={handleClickNow}
          />

          <BranchSelector />

          <AccountMenu />
        </div>
      </div>
    </div>
  );
}
