import Accordion from "@/components/display/accordion";
import { classNames } from "@/utils/common";
import { DiffNodeElement } from "./node-element";
import { DiffDisplay, DiffTitle } from "./utils";
import { DiffThread } from "./thread";
import { useParams } from "react-router-dom";

type DiffNodeRelationshipProps = {
  relationship: any;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <DiffTitle containsConflict={relationship.contains_conflict} status={relationship.status}>
      <div className="flex flex-1 items-center">
        <div className="flex items-center w-1/3 font-normal text-xs">
          {relationship.name}

          {!branchName && relationship.path_identifier && (
            <DiffThread path={relationship.path_identifier} />
          )}
        </div>

        <div className="w-2/3">
          <DiffDisplay />
        </div>
      </div>
    </DiffTitle>
  );

  return (
    <div
      className={classNames(
        "bg-custom-white relative",
        relationship.contains_conflict && "bg-yellow-50"
      )}>
      <div
        className={classNames(
          "absolute top-0 bottom-0 left-0 w-1",
          relationship.contains_conflict && "bg-yellow-200"
        )}
      />
      <Accordion title={title}>
        {relationship.elements.map((element, index: number) => (
          <DiffNodeElement key={index} element={element} />
        ))}
      </Accordion>
    </div>
  );
};
