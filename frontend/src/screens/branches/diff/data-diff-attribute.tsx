import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeAttribute, tDataDiffNodeProperty } from "./data-diff-node";
import { Badge } from "../../../components/badge";
import { diffContent } from "../../../utils/diff";

export type tDataDiffNodeAttributeProps = {
  attribute: tDataDiffNodeAttribute,
}

export const DataDiffAttribute = (props: tDataDiffNodeAttributeProps) => {
  const { attribute } = props;

  const {
    action,
    name,
    changed_at,
    properties
  } = attribute;

  const property = properties?.find((p) => p.type === "HAS_VALUE");

  const titleContent = (
    <div className="p-2 pr-0 hover:bg-gray-50 grid grid-cols-3 gap-4">
      <div className="flex">
        <Badge>
          Attribute
        </Badge>

        <span className="mr-2 font-semibold">
          {name}
        </span>
      </div>

      <div className="flex">
        <span className="font-semibold">
          {diffContent[action](property)}
        </span>
      </div>

      <div className="flex justify-end">
        {/* <DiffPill /> */}

        {
          changed_at
          && (
            <DateDisplay date={changed_at} hideDefault />
          )
        }
      </div>
    </div>
  );

  return (
    <div className="flex flex-col">
      <Accordion title={titleContent}>
        <div className="divide-y">
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