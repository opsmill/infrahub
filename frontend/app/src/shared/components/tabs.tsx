import { parseAsString, useQueryState } from "nuqs";

import { Pill } from "@/shared/components/display/pill";
import { QSP } from "@/shared/config/qsp";
import { classNames } from "@/shared/utils/common";

import { ScrollArea } from "./ui/scroll-area";

type Tab = {
  name: string;
  label?: string;
  count?: number;
  onClick?: Function;
};

type TabsProps = {
  tabs: Tab[];
  rightItems?: any;
  qsp?: string;
  className?: string;
};

export const Tabs = (props: TabsProps) => {
  const { qsp, tabs, rightItems, className } = props;

  const [qspTab, setQspTab] = useQueryState(
    qsp ?? QSP.TAB,
    parseAsString.withOptions({ history: "push", shallow: false })
  );

  const handleClick = (tab: Tab, index: number) => {
    if (tab.onClick) {
      return tab.onClick();
    }

    setQspTab(index === 0 ? null : tab.name);
  };

  return (
    <div
      className={classNames("flex items-center border-gray-200 border-b bg-white px-2", className)}
    >
      <ScrollArea scrollX className="flex-1">
        <nav className="flex space-x-8 px-4" aria-label="Tabs">
          {tabs.map((tab: Tab, index: number) => {
            return (
              <div
                key={tab.name}
                onClick={() => handleClick(tab, index)}
                className={classNames(
                  "flex cursor-pointer items-center whitespace-nowrap border-gray-200 border-b-2 px-1 py-4 font-medium text-sm",
                  (qspTab && qspTab === tab.name) || (!qspTab && index === 0) // First item is active without QSP
                    ? "border-custom-blue-500 text-custom-blue-600"
                    : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                )}
              >
                {tab.label}

                {tab.count !== undefined && (
                  <Pill className="ml-2" data-cy="tab-counter">
                    {JSON.stringify(tab.count)}
                  </Pill>
                )}
              </div>
            );
          })}
        </nav>
      </ScrollArea>

      <div>{rightItems}</div>
    </div>
  );
};
