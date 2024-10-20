import { Pill } from "@/components/display/pill";
import { QSP } from "@/config/qsp";
import { classNames } from "@/utils/common";
import { StringParam, useQueryParam } from "use-query-params";

type Tab = {
  name?: string;
  label?: string;
  count?: number;
  onClick?: Function;
  component?: Function | null;
};

type TabsProps = {
  tabs: Tab[];
  rightItems?: any;
  qsp?: string;
  className?: string;
};

export const Tabs = (props: TabsProps) => {
  const { qsp, tabs, rightItems, className } = props;

  const [qspTab, setQspTab] = useQueryParam(qsp ?? QSP.TAB, StringParam);

  const handleClick = (tab: Tab, index: number) => {
    if (tab.onClick) {
      return tab.onClick();
    }

    setQspTab(index === 0 ? undefined : tab.name);
  };

  return (
    <div
      className={classNames(
        "bg-custom-white flex items-center border-b border-gray-200 px-2",
        className
      )}
    >
      <div className="flex-1">
        <nav className="-mb-px flex space-x-8 px-4" aria-label="Tabs">
          {tabs.map((tab: Tab, index: number) => {
            const Component = tab.component ? tab.component : () => null;

            return (
              <div
                key={tab.name}
                onClick={() => handleClick(tab, index)}
                className={classNames(
                  "flex items-center whitespace-nowrap border-b-2 py-4 px-1 text-sm font-medium cursor-pointer",
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

                <Component />
              </div>
            );
          })}
        </nav>
      </div>
      <div>{rightItems}</div>
    </div>
  );
};
