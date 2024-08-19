import { MouseEventHandler } from "react";
import { Button } from "./button-primitive";

type Tab = {
  label?: string;
  isActive?: boolean;
  onClick: MouseEventHandler;
};

type TabsProps = {
  tabs: Tab[];
  isLoading?: boolean;
};

export const ToggleButtons = (props: TabsProps) => {
  const { tabs, isLoading } = props;

  return (
    <div className="flex items-center">
      <div className="isolate inline-flex rounded-md shadow-sm border border-gray-300 overflow-hidden">
        {tabs.map((tab: Tab) => (
          <Button
            key={tab.label}
            onClick={tab.onClick}
            variant={tab.isActive ? "active" : "outline"}
            className={"cursor-pointer border-0 px-4 py-2 rounded-none"}
            isLoading={isLoading}>
            {tab.label}
          </Button>
        ))}
      </div>
    </div>
  );
};
