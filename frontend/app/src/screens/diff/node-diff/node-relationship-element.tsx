import { BadgeConflict } from "@/screens/diff/diff-badge";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffRelationshipElement, DiffStatus } from "@/screens/diff/node-diff/types";
import { DiffBadge, DiffRow } from "@/screens/diff/node-diff/utils";
import { useParams } from "react-router-dom";
import { DiffNodeProperty } from "./node-property";

type DiffNodeElementProps = {
  element: DiffRelationshipElement;
  status: DiffStatus;
};

export const DiffNodeRelationshipElement = ({ element, status }: DiffNodeElementProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      status={status}
      iconClassName="left-4"
      title={
        <div className="flex items-center justify-between pl-4 pr-2">
          <div className="flex gap-1 py-2">
            <DiffBadge size="icon" status={element.status} className="p-0.5" /> {element.peer_label}
            {element.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && element.path_identifier && <DiffThread path={element.path_identifier} />}
        </div>
      }
      right={element.status === "ADDED" && element.peer_label}
      left={element.status === "REMOVED" && element.peer_label}
    >
      <div className="divide-y border-t">
        {element.properties
          .filter((property) => property.status !== "UNCHANGED")
          .map((property, index) => (
            <DiffNodeProperty key={index} property={property} status={status} className="pl-8" />
          ))}
      </div>
    </DiffRow>
  );
};
