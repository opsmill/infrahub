import { ReactNode } from "react";
import { StringParam, useQueryParam } from "use-query-params";

import { QSP } from "@/config/qsp";

import { Button } from "./button-primitive";

type Tab = {
  name?: string;
  label?: ReactNode;
  disabled?: boolean;
};

type TabsProps = {
  tabs: Tab[];
  rightItems?: any;
  qsp?: string;
};

export const TabsButtons = (props: TabsProps) => {
  const { tabs, rightItems, qsp } = props;

  const [qspTab, setQspTab] = useQueryParam(qsp ?? QSP.TAB, StringParam);

  return (
    <div className="flex items-center bg-white">
      <div className="isolate inline-flex overflow-hidden rounded-md border border-gray-300 shadow-xs">
        {tabs.map((tab: Tab, index: number) => (
          <Button
            key={tab.name}
            onClick={() => setQspTab(index === 0 ? undefined : tab.name)}
            variant={
              (qspTab && qspTab === tab.name) || (!qspTab && index === 0) ? "active" : "outline"
            }
            disabled={tab.disabled}
            className={"rounded-none border-0 px-4 py-2"}
          >
            {tab.label}
          </Button>
        ))}
        <div>{rightItems}</div>
      </div>
    </div>
  );
};
