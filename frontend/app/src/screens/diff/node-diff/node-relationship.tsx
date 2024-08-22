import { classNames } from "@/utils/common";
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
    <div
      className={classNames(
        "bg-custom-white relative",
        relationship.contains_conflict && "bg-yellow-50"
      )}>
      {relationship.contains_conflict && (
        <div className="absolute top-0 bottom-0 left-0 w-0.5 bg-yellow-400" />
      )}

      <DiffRow
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
    </div>
  );
};
