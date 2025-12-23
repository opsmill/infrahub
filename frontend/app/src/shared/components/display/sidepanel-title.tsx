import { Icon } from "@iconify-icon/react";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";

type tSidePanelTitle = {
  title: string;
  children: any;
  hideBranch?: boolean;
};

export const SidePanelTitle = (props: tSidePanelTitle) => {
  const { title, children, hideBranch } = props;

  const { currentBranch } = useCurrentBranch();

  return (
    <div className="space-y-2">
      <div className="flex w-full items-center">
        <span className="mr-3 font-semibold text-lg">{title}</span>
        <div className="flex-1"></div>
        {!hideBranch && (
          <div className="flex items-center">
            <Icon icon={"mdi:layers-triple"} />
            <div className="ml-1.5 pb-1">{currentBranch.name}</div>
          </div>
        )}
      </div>
      {children}
    </div>
  );
};
