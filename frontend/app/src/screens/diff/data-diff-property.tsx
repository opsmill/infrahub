import { classNames } from "@/utils/common";
import { diffContent } from "@/utils/diff";
import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useParams } from "react-router-dom";
import { tDataDiffNodePropertyChange } from "./data-diff-node";
import { DataDiffThread } from "./diff-thread";

export type tDataDiffNodePropertyProps = {
  property: tDataDiffNodePropertyChange;
  path: string;
};

export const DataDiffProperty = (props: tDataDiffNodePropertyProps) => {
  const { property, path } = props;

  const { "*": branchName } = useParams();

  const { type, action, branch } = property;

  return (
    <div className="relative flex group">
      {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
      <ChevronDownIcon className="w-4 h-4 mx-2 text-transparent" aria-hidden="true" />

      <div className={classNames("flex-1 flex flex-col lg:flex-row")}>
        <div className="flex flex-1 items-center">
          <div className="flex w-1/3 items-center group">
            <span className="">{type}</span>

            {/* Do not display comment button if we are on the branch details view */}
            {!branchName && <DataDiffThread path={path} />}
          </div>

          <div className="flex w-2/3 items-center">
            <span className="pl-2 flex items-center w-1/2 font-semibold bg-green-700/10">
              {branch === "main" && diffContent[action](property)}
            </span>
            <span className="pl-2 flex items-center w-1/2 font-semibold bg-custom-blue-700/10">
              {branch !== "main" && diffContent[action](property)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
