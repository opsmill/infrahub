import { StringParam, useQueryParam } from "use-query-params";
import { BUTTON_TYPES, Button } from "./button";
import { QSP } from "../config/qsp";
import { classNames } from "../utils/common";

type Tab = {
  name?: string;
  label?: string;
}

type TabsProps = {
  tabs: Tab[];
  rightItems?: any,
  qsp?: string,
}

const getClassName = (firstItem: boolean, lastItem: boolean): string => {
  if (firstItem) {
    return "rounded-l-md";
  }

  if (lastItem) {
    return "rounded-r-md";
  }

  return "rounded-none";
};

export const TabsButtons = (props: TabsProps) => {
  const { tabs, rightItems, qsp} = props;

  const [qspTab, setQspTab] = useQueryParam(qsp ?? QSP.TAB, StringParam);

  return (
    <div className="bg-white flex items-center">
      <div className="isolate inline-flex rounded-md shadow-sm ring-1 ring-gray-300 m-4">
        {
          tabs
          .map(
            (tab: Tab, index: number) => (
              <Button
                key={tab.name}
                onClick={() => setQspTab(index === 0 ? undefined : tab.name)}
                buttonType={
                  (qspTab && qspTab === tab.name) || (!qspTab && index === 0)
                    ? BUTTON_TYPES.ACTIVE
                    : undefined
                }
                className={
                  classNames(
                    "ring-0 px-4 py-2",
                    getClassName(index === 0, index === tabs.length -1)
                  )
                }
              >
                {tab.label}
              </Button>
            )
          )
        }
        <div>
          {rightItems}
        </div>
      </div>
    </div>
  );
};