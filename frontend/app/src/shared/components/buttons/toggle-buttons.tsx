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
      <div className="isolate inline-flex overflow-hidden rounded-md border border-gray-300 shadow-xs">
        {tabs.map((tab: Tab) => (
          <Button
            key={tab.label}
            onClick={tab.onClick}
            size={"sm"}
            variant={tab.isActive ? "active" : "ghost"}
            className={"cursor-pointer rounded-none border-0 px-4 py-2"}
            {...props}
          >
            {tab.label}
          </Button>
        ))}
      </div>
    </div>
  );
};
