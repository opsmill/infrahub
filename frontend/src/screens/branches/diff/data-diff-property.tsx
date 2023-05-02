import { DateDisplay } from "../../../components/date-display";
import { tDataDiffNodeProperty } from "./data-diff-node";
import { diffContent } from "../../../utils/diff";

export type tDataDiffNodePropertyProps = {
  property: tDataDiffNodeProperty,
}

export const DataDiffProperty = (props: tDataDiffNodePropertyProps) => {
  const { property } = props;

  const {
    type,
    action,
    changed_at,
  } = property;

  return (
    <div className="p-1 pr-0 grid grid-cols-3 gap-4">
      <div className="flex items-center">
        <span className="mr-4">
          {type}
        </span>
      </div>

      <div className="flex items-center">
        {diffContent[action](property)}
      </div>

      <div className="flex items-center justify-end">
        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>
    </div>
  );
};