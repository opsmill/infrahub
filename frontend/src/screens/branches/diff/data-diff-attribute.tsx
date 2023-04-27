import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeAttribute, tDataDiffNodeProperty } from "./data-diff-node";

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
    <div className="flex flex-col pl-4">
      <Accordion title={
        (
          <div className="flex">
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
        )
      }>
        <div className="divide-y border">
          {
            properties
            ?.map(
              (property: tDataDiffNodeProperty, index: number) => <DataDiffProperty key={index} property={property} />
            )
          }
        </div>
      </Accordion>
    </div>

  );
};