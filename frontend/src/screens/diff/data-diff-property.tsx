import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { DateDisplay } from "../../components/date-display";
import { QSP } from "../../config/qsp";
import { classNames } from "../../utils/common";
import { diffContent } from "../../utils/diff";
import { getNodeClassName, tDataDiffNodePropertyChange } from "./data-diff-node";
import { DataDiffThread } from "./diff-thread";

export type tDataDiffNodePropertyProps = {
  property: tDataDiffNodePropertyChange;
  path: string;
};

export const DataDiffProperty = (props: tDataDiffNodePropertyProps) => {
  const { property, path } = props;

  const { branchname } = useParams();
  const [branchOnly] = useQueryParam(QSP.BRANCH_FILTER_BRANCH_ONLY, StringParam);

  const { type, action, changed_at, branch } = property;

  return (
    <div className="flex">
      {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
      <ChevronDownIcon className="h-5 w-5 mr-2 text-transparent" aria-hidden="true" />

      <div
        className={classNames(
          "flex-1 p-1 pr-0 grid grid-cols-3 gap-4",
          getNodeClassName([], branch, branchOnly)
        )}>
        <div className="flex items-center group">
          <span className="mr-4">{type}</span>

          {/* Do not display comment button if we are on the branch details view */}
          {!branchname && <DataDiffThread path={path} />}
        </div>

        <div className="flex items-center">{diffContent[action](property)}</div>

        <div className="flex items-center justify-end">
          <div className="min-w-[330px]">
            {changed_at && <DateDisplay date={changed_at} hideDefault />}
          </div>
        </div>
      </div>
    </div>
  );
};
