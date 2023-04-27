import Accordion from "../../../components/accordion";
import { DateDisplay } from "../../../components/date-display";
import { DataDiffProperty } from "./data-diff-property";
import { getBadgeType, tDataDiffNodeProperty, tDataDiffNodeRelationship } from "./data-diff-node";
import { DataDiffPeer } from "./data-diff-peer";
import { Badge } from "../../../components/badge";

export type tDataDiffNodeRelationshipProps = {
  relationship: tDataDiffNodeRelationship,
}

export const DataDiffRelationship = (props: tDataDiffNodeRelationshipProps) => {
  const { relationship } = props;

  const {
    branch,
    action,
    name,
    changed_at,
    properties,
    peer
  } = relationship;

  const titleContent = (
    <div className="flex">
      <Badge className="mr-2" type={getBadgeType(action)}>
        {action?.toUpperCase()}
      </Badge>

      <Badge>
        {name}
      </Badge>

      {
        peer
        && (
          <DataDiffPeer peer={peer} branch={branch} />
        )
      }

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