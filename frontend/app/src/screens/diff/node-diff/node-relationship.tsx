import { DiffNodeRelationshipElement } from "./node-relationship-element";
import { useParams } from "react-router-dom";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffRow } from "@/screens/diff/node-diff/utils";
import { DiffRelationship } from "@/screens/diff/node-diff/types";

type DiffNodeRelationshipProps = {
  relationship: DiffRelationship;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const { "*": branchName } = useParams();

  return (
    <DiffRow
      hasConflicts={relationship.contains_conflict}
      title={
        <div className="flex justify-between items-center pr-2">
          <div className="p-2">{relationship.label}</div>

          {!branchName && relationship.path_identifier && (
            <DiffThread path={relationship.path_identifier} />
          )}
        </div>
      }>
      {relationship.elements.map((element, index: number) => (
        <DiffNodeRelationshipElement key={index} element={element} />
      ))}
    </DiffRow>
  );
};
