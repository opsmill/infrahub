import { StringParam, useQueryParam } from "use-query-params";
import { classNames } from "../utils/common";
import { QSP } from "../config/qsp";

type Tab = {
  name?: string;
  label?: string;
};

type TabsProps = {
  tabs: Tab[];
  rightItems?: any;
  qsp?: string;
};

export const Tabs = (props: TabsProps) => {
  const [qspTab, setQspTab] = useQueryParam(props.qsp ?? QSP.TAB, StringParam);

  return (
    <div className="bg-white flex items-center border-b border-gray-200">
      <div className="flex-1">
        <div className="">
          <nav className="-mb-px flex space-x-8 px-4" aria-label="Tabs">
            {props.tabs.map((tab: Tab, index: number) => (
              <div
                key={tab.name}
                onClick={() => setQspTab(index === 0 ? undefined : tab.name)}
                className={classNames(
                  (qspTab && qspTab === tab.name) || (!qspTab && index === 0) // First item is active without QSP
                    ? "border-indigo-500 text-indigo-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700",
                  "whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium cursor-pointer"
                )}>
                {tab.label}
              </div>
            ))}
          </nav>
        </div>
      </div>
      <div>{props.rightItems}</div>
    </div>
  );
};
