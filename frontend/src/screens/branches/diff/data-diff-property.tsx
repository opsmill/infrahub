import { ChevronDownIcon } from "@heroicons/react/24/outline";
import { DateDisplay } from "../../../components/date-display";
import { classNames } from "../../../utils/common";
import { diffContent } from "../../../utils/diff";
import { tDataDiffNodePropertyChange } from "./data-diff-node";

export type tDataDiffNodePropertyProps = {
  property: tDataDiffNodePropertyChange;
};

export const DataDiffProperty = (props: tDataDiffNodePropertyProps) => {
  const { property } = props;

  const { type, action, changed_at, branch } = property;

  return (
    <div className="flex">
      {/* Align with transparent chevron to fit the UI with other accordions with visible chevrons */}
      <ChevronDownIcon className="h-5 w-5 mr-2 text-transparent" aria-hidden="true" />

      <div
        className={classNames(
          "flex-1 p-2 pr-0 grid grid-cols-3 gap-4",
          branch === "main" ? "bg-custom-blue-10" : "bg-green-200"
        )}>
        <div className="flex items-center">
          <span className="mr-4">{type}</span>
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
