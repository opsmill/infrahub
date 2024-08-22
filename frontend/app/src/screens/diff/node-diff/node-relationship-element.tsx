import { DiffNodeProperty } from "./node-property";
import { DiffRelationshipElement } from "@/screens/diff/node-diff/types";
import { DiffBadge, DiffRow } from "@/screens/diff/node-diff/utils";
import { BadgeConflict } from "@/screens/diff/diff-badge";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";

type DiffNodeElementProps = {
  element: DiffRelationshipElement;
};

export const DiffNodeRelationshipElement = ({ element }: DiffNodeElementProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      title={
        <div className="flex items-center justify-between pl-8 pr-2">
          <div className="flex gap-1 py-2">
            <DiffBadge icon status={element.status} className="p-0.5" /> {element.peer_label}
            {element.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && element.path_identifier && <DiffThread path={element.path_identifier} />}
        </div>
      }
      right={
        element.status === "ADDED" && (
          <Badge variant="blue" className="bg-transparent">
            {element.peer_label}
          </Badge>
        )
      }
      left={
        element.status === "REMOVED" && (
          <Badge variant="green" className="bg-transparent">
            {element.peer_label}
          </Badge>
        )
      }>
      {element.properties
        .filter((property) => property.status !== "UNCHANGED")
        .map((property, index) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
    </DiffRow>
  );
};
