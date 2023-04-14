import { DateDisplay } from "../../../components/date-display";
import { DataDiffAttributeProperty } from "./data-diff-attribute-property";
import { tDataDiffNodeAttribute, tDataDiffNodeAttributeProperty } from "./data-diff-node";

export type tDataDiffNodeAttributeProps = {
  attribute: tDataDiffNodeAttribute,
}

export const DataDiffAttribute = (props: tDataDiffNodeAttributeProps) => {
  const { attribute } = props;

  const {
    name,
    changed_at,
    properties
  } = attribute;

  return (
    <div className="ml-4 p-2 pb-0 flex flex-col border-l border-gray-200">
      <div className="ml-4">
        <span className="mr-2 font-semibold">
          {name}
        </span>

        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>

      <div className="">
        {
          properties
          ?.map(
            (property: tDataDiffNodeAttributeProperty, index: number) => <DataDiffAttributeProperty key={index} property={property} />
          )
        }
      </div>
    </div>

  );
};