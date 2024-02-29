import { BUTTON_TYPES, Button } from "./button";

type Tab = {
  label?: string;
  isActive?: boolean;
  onClick: Function;
};

type TabsProps = {
  tabs: Tab[];
  isLoading?: boolean;
};

export const ToggleButtons = (props: TabsProps) => {
  const { tabs, isLoading } = props;

  return (
    <div className="flex items-center">
      <div className="isolate inline-flex rounded-md shadow-sm border border-gray-300 m-4 overflow-hidden">
        {tabs.map((tab: Tab) => (
          <Button
            key={tab.label}
            onClick={tab.onClick}
            buttonType={tab.isActive ? BUTTON_TYPES.ACTIVE : undefined}
            className={"cursor-pointer border-0 px-4 py-2 rounded-none"}
            isLoading={isLoading}>
            {tab.label}
          </Button>
        ))}
      </div>
    </div>
  );
};
