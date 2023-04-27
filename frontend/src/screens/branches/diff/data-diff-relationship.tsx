import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { tDataDiffNodeProperty, tDataDiffNodeRelationship } from "./data-diff-node";
import { DataDiffPeer } from "./data-diff-peer";
import { DiffPill } from "./diff-pill";

export type tDataDiffNodeRelationshipProps = {
  relationship: tDataDiffNodeRelationship,
}

export const DataDiffRelationship = (props: tDataDiffNodeRelationshipProps) => {
  const { relationship } = props;

  const {
    branch,
    changed_at,
    properties,
    peer
  } = relationship;

  const titleContent = (
    <div className="flex hover:bg-gray-50">
      <div className="flex flex-1">
        {
          peer
          && (
            <DataDiffPeer peer={peer} branch={branch} />
          )
        }
      </div>

      <DiffPill />

      {
        changed_at
        && (
          <DateDisplay date={changed_at} hideDefault />
        )
      }
    </div>
  );

  return (
    <div className="flex flex-col pl-4">
      {
        properties
        ?.length
          ? (
            <Accordion title={titleContent}>
              <div>
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