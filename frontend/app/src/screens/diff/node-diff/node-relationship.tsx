import Accordion from "@/components/display/accordion";
import { classNames } from "@/utils/common";
import { DiffNodeElement } from "./node-element";
import { DiffRow } from "./utils";
import { DiffThread } from "./thread";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";

type DiffNodeRelationshipProps = {
  relationship: any;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const { "*": branchName } = useParams();

  const title = (
    <DiffRow
      title={
        <div className="flex justify-between items-center pr-2">
          <div className="p-2">{relationship.label}</div>

          {!branchName && relationship.path_identifier && (
            <DiffThread path={relationship.path_identifier} />
          )}
        </div>
      }
      left={<Badge variant="green">{}</Badge>}
      right={<Badge variant="green">{}</Badge>}
    />
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
