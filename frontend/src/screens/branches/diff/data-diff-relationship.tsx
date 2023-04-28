import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeProperty, tDataDiffNodeRelationship } from "./data-diff-node";
import { DiffPill } from "./diff-pill";
import { Badge } from "../../../components/badge";
import { diffContent } from "../../../utils/diff";

export type tDataDiffNodeRelationshipProps = {
  relationship: tDataDiffNodeRelationship,
}

export const DataDiffRelationship = (props: tDataDiffNodeRelationshipProps) => {
  const { relationship } = props;

  const {
    action,
    changed_at,
    properties,
    peer
  } = relationship;

  console.log("properties: ", properties);
  const property = properties?.find((p) => p.type === "HAS_VALUE");

  const titleContent = (
    <div className="p-2 pr-0 hover:bg-gray-50 grid grid-cols-3 gap-4">
      <div className="flex">
        <Badge>
          {peer?.kind}
        </Badge>

        <span className="mr-2 font-semibold">
          {peer?.display_label}
        </span>
      </div>

      <div className="flex">
        <span className="font-semibold">
          {
            action
            && property
            && diffContent[action](property)
          }
        </span>
      </div>

      <div className="flex justify-end">
        <DiffPill />

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
      {
        properties
        ?.length
          ? (
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
          )
          : (
            <div className="m-2">
              {titleContent}
            </div>
          )
      }
    </div>

  );
};