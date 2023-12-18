import { Icon } from "@iconify-icon/react";
import { DEFAULT_BRANCH_NAME } from "../config/constants";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "../state/atoms/branches.atom";

type tSidePanelTitle = {
  title: string;
  children: any;
  hideBranch?: boolean;
};

export const SidePanelTitle = (props: tSidePanelTitle) => {
  const { title, children, hideBranch } = props;

  const branch = useAtomValue(currentBranchAtom);

  return (
    <div className="space-y-2">
      <div className="flex items-center w-full">
        <span className="text-lg font-semibold mr-3">{title}</span>
        <div className="flex-1"></div>
        {!hideBranch && (
          <div className="flex items-center">
            <Icon icon={"mdi:layers-triple"} />
            <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
          </div>
        )}
      </div>
      {children}
    </div>
  );
};
