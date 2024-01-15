import { StringParam, useQueryParam } from "use-query-params";
import { QSP } from "../../config/qsp";
import { BUTTON_TYPES, Button } from "./button";

type Tab = {
  name?: string;
  label?: string;
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
    <div className="bg-custom-white flex items-center">
      <div className="isolate inline-flex rounded-md shadow-sm border border-gray-300 m-4 overflow-hidden">
        {tabs.map((tab: Tab, index: number) => (
          <Button
            key={tab.name}
            onClick={() => setQspTab(index === 0 ? undefined : tab.name)}
            buttonType={
              (qspTab && qspTab === tab.name) || (!qspTab && index === 0)
                ? BUTTON_TYPES.ACTIVE
                : undefined
            }
            className={"border-0 px-4 py-2 rounded-none"}>
            {tab.label}
          </Button>
        ))}
        <div>{rightItems}</div>
      </div>
    </div>
  );
};
