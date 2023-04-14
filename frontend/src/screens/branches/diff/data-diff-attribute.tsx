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
    <div className="flex flex-col">
      <div className="">
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

      <div className="divide-y border">
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