import { formatISO, isEqual, isValid } from "date-fns";
import { useAtom, useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";
import { StringParam, useQueryParam } from "use-query-params";
import BranchSelector from "../../components/branch-selector";
import { DatePicker } from "../../components/inputs/date-picker";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { CONFIG } from "../../config/config";
import { QSP } from "../../config/qsp";
import { ReactComponent as InfrahubLogo } from "../../images/Infrahub-SVG-hori.svg";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { currentSchemaHashAtom } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import { debounce } from "../../utils/common";
import { fetchUrl } from "../../utils/fetch";
import LoadingScreen from "../loading-screen/loading-screen";
import DropDownMenuHeader from "./desktop-menu-header";
import { Footer } from "./footer";

export default function DesktopMenu() {
  const branch = useAtomValue(currentBranchAtom);
  const currentSchemaHash = useAtomValue(currentSchemaHashAtom);
  const [qspDate, setQspDate] = useQueryParam(QSP.DATETIME, StringParam);
  const [date, setDate] = useAtom(datetimeAtom);

  const [isLoading, setIsLoading] = useState(false);
  const [menu, setMenu] = useState([]);

  const fetchMenu = async () => {
    if (!currentSchemaHash) return;

    try {
      setIsLoading(true);

      const result = await fetchUrl(CONFIG.MENU_URL(branch?.name));

      setMenu(result);

      setIsLoading(false);
    } catch (error) {
      console.error("error: ", error);
      toast(<Alert type={ALERT_TYPES.ERROR} message="Error while fetching the menu" />);
      setIsLoading(false);
    }
  };

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

  useEffect(() => {
    fetchMenu();
  }, [currentSchemaHash]);

  return (
    <div className="z-100 hidden w-64 md:visible md:inset-y-0 md:flex md:flex-col">
      <div className="flex flex-grow flex-col overflow-y-auto border-r border-gray-200 bg-custom-white">
        <Link to="/" className="p-4">
          <InfrahubLogo className="w-full" />
        </Link>

        <div className="flex flex-col items-stretch">
          <div className="p-2 pb-0">
            <DatePicker
              date={date}
              onChange={debouncedHandleDateChange}
              onClickNow={handleClickNow}
            />
          </div>

          <div className="p-2">
            <BranchSelector />
          </div>
        </div>

        <div className="flex flex-grow flex-col flex-1 overflow-auto">
          {isLoading && <LoadingScreen size={32} hideText />}

          {!isLoading && (
            <nav
              className="flex-1 bg-custom-white divide-y"
              aria-label="Sidebar"
              data-cy="sidebar-menu"
              data-testid="sidebar-menu">
              {menu.map((item: any, index: number) => (
                <DropDownMenuHeader
                  key={index}
                  title={item.title}
                  items={item.children}
                  icon={item.icon}
                />
              ))}
            </nav>
          )}
        </div>
      </div>

      <Footer />
    </div>
  );
}
