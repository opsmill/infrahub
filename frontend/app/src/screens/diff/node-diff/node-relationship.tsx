import { DiffNodeRelationshipElement } from "./node-relationship-element";
import { useParams } from "react-router-dom";
import { DiffThread } from "@/screens/diff/node-diff/thread";
import { DiffRow } from "@/screens/diff/node-diff/utils";
import { DiffRelationship } from "@/screens/diff/node-diff/types";
import { Badge } from "@/components/ui/badge";
import { Icon } from "@iconify-icon/react";

type DiffNodeRelationshipProps = {
  relationship: DiffRelationship;
};

export const DiffNodeRelationship = ({ relationship }: DiffNodeRelationshipProps) => {
  const { "*": branchName } = useParams();

  const AddedCount = relationship.elements.filter(({ status }) => status === "ADDED").length;
  const RemovedCount = relationship.elements.filter(({ status }) => status === "REMOVED").length;
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
      }
      right={
        <div className="space-x-1">
          <Badge variant="red" className="gap-1">
            <Icon icon="mdi:minus-circle-outline" />
            {RemovedCount}
          </Badge>
          <Badge variant="green" className="gap-1">
            <Icon icon="mdi:plus-circle-outline" />
            {AddedCount}
          </Badge>
        </div>
      }>
      {relationship.elements.map((element, index: number) => (
        <DiffNodeRelationshipElement key={index} element={element} />
      ))}
    </DiffRow>
  );
};
