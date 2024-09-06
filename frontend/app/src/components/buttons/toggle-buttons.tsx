import { MouseEventHandler } from "react";
import { Button, ButtonProps } from "./button-primitive";

type Tab = {
  label?: string;
  isActive?: boolean;
  onClick: MouseEventHandler;
};

interface TabsProps extends ButtonProps {
  tabs: Tab[];
  isLoading?: boolean;
}

export const ToggleButtons = ({ tabs, ...props }: TabsProps) => {
  return (
    <div className="flex items-center">
      <div className="isolate inline-flex rounded-md shadow-sm border border-gray-300 overflow-hidden">
        {tabs.map((tab: Tab) => (
          <Button
            key={tab.label}
            onClick={tab.onClick}
            size={"sm"}
            variant={tab.isActive ? "active" : "ghost"}
            className={"cursor-pointer border-0 px-4 py-2 rounded-none"}
            {...props}>
            {tab.label}
          </Button>
        ))}
      </div>
    </div>
  );
};
