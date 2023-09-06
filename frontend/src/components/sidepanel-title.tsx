import { useReactiveVar } from "@apollo/client";
import { Square3Stack3DIcon } from "@heroicons/react/24/outline";
import { DEFAULT_BRANCH_NAME } from "../config/constants";
import { branchVar } from "../graphql/variables/branchVar";

type tSidePanelTitle = {
  title: string;
  children: any;
  hideBranch?: boolean;
};

export const SidePanelTitle = (props: tSidePanelTitle) => {
  const { title, children, hideBranch } = props;

  const branch = useReactiveVar(branchVar);

  return (
    <div className="space-y-2">
      <div className="flex items-center w-full">
        <span className="text-lg font-semibold mr-3">{title}</span>
        <div className="flex-1"></div>
        {!hideBranch && (
          <div className="flex items-center">
            <Square3Stack3DIcon className="w-5 h-5" />
            <div className="ml-1.5 pb-1">{branch?.name ?? DEFAULT_BRANCH_NAME}</div>
          </div>
        )}
      </div>
      {children}
    </div>
  );
};
