import type { ReactNode } from "react";
import { Link, useMatch } from "react-router";

import { Pill } from "@/shared/components/display/pill";
import { classNames } from "@/shared/utils/common";

type TabProps = {
  to: string;
  label: ReactNode;
  count?: number;
  component?: Function | null;
  isLoading?: boolean;
  error?: boolean;
};

function Tab({ to, label, isLoading, error, count }: TabProps) {
  const match = useMatch(to.split("?")[0] as string);

  return (
    <Link
      to={to}
      className={classNames(
        "flex cursor-pointer items-center whitespace-nowrap border-gray-200 border-b-2 px-4 py-2 font-medium text-sm",
        match
          ? "border-custom-blue-500 bg-custom-blue-600/10 text-custom-blue-600"
          : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
      )}
    >
      {label}

      <Pill className="ml-2" data-cy="tab-counter" isLoading={isLoading} error={error}>
        {count}
      </Pill>
    </Link>
  );
}

type TabsProps = {
  tabs: TabProps[];
  rightItems?: any;
  qsp?: string;
  className?: string;
};

export function Tabs(props: TabsProps) {
  const { tabs, rightItems, className } = props;

  return (
    <div className={classNames("flex items-center border-gray-200 border-b bg-white", className)}>
      <div className="flex-1">
        <div className="">
          <nav className="-mb-px flex" aria-label="Tabs">
            {tabs.map((tab: TabProps, index: number) => {
              return <Tab {...tab} key={index} />;
            })}
          </nav>
        </div>
      </div>
      <div>{rightItems}</div>
    </div>
  );
}
