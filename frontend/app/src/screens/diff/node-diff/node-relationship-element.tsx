import { DiffNodeProperty } from "./node-property";
import { DiffRelationshipElement } from "@/screens/diff/node-diff/types";
import { DiffRow } from "@/screens/diff/node-diff/utils";
import { BadgeConflict } from "@/screens/diff/diff-badge";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { useParams } from "react-router-dom";

type DiffNodeElementProps = {
  element: DiffRelationshipElement;
};

export const DiffNodeRelationshipElement = ({ element }: DiffNodeElementProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      title={
        <div className="flex items-center justify-between pl-8 pr-2">
          <div className="flex items-center gap-2 py-2">
            {element.peer_label}
            {element.conflict && <BadgeConflict>Conflict</BadgeConflict>}
          </div>

          {!branchName && element.path_identifier && <DiffThread path={element.path_identifier} />}
        </div>
      }>
      {element.properties
        .filter((property) => property.status !== "UNCHANGED")
        .map((property, index) => (
          <DiffNodeProperty key={index} property={property} />
        ))}
    </DiffRow>
  );
};
