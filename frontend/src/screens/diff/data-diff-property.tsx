import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { useParams } from "react-router-dom";
import { StringParam, useQueryParam } from "use-query-params";
import { DateDisplay } from "../../components/display/date-display";
import { QSP } from "../../config/qsp";
import { classNames } from "../../utils/common";
import { diffContent } from "../../utils/diff";
import { getNodeClassName, tDataDiffNodePropertyChange } from "./data-diff-node";
import { DataDiffConflictInfo } from "./diff-conflict-info";
import { DiffPill } from "./diff-pill";
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
    <div className="relative flex group">
      {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
      <ChevronDownIcon className="w-4 h-4 mr-2 text-transparent" aria-hidden="true" />

      <div
        className={classNames(
          "p-1 pr-0 flex-1 flex flex-col lg:flex-row rounded-md mb-1",
          getNodeClassName([], branch, branchOnly)
        )}>
        <div className="flex flex-1 items-center">
          <div className="flex flex-1 items-center group">
            <span className="">{type}</span>

            {/* Do not display comment button if we are on the branch details view */}
            {!branchname && <DataDiffThread path={path} />}
          </div>

          <div className="flex flex-1 items-center">{diffContent[action](property)}</div>
        </div>

        <div className="flex flex-1 lg:justify-end items-center mt-2 lg:mt-0">
          <DiffPill hidden />

          <div className="flex lg:w-[200px]">
            {/* {changed_at && <DateDisplay date={changed_at} hideDefault />} */}
            <DateDisplay date={changed_at} />
          </div>
        </div>
      </div>

      {!branchname && <DataDiffConflictInfo path={path} />}
    </div>
  );
};
