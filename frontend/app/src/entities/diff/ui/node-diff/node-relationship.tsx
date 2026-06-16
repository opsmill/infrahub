import { Icon } from "@iconify-icon/react";
import { useParams } from "react-router";

import { Badge } from "@/shared/components/ui/badge";

import { DiffThread } from "@/entities/diff/ui/node-diff/thread";
import type { DiffRelationship, DiffStatus } from "@/entities/diff/ui/node-diff/types";
import { DiffRow } from "@/entities/diff/ui/node-diff/utils";

import { DiffNodeRelationshipElement } from "./node-relationship-element";

type DiffNodeRelationshipProps = {
  relationship: DiffRelationship;
  status: DiffStatus;
};

export const DiffNodeRelationship = ({ status, relationship }: DiffNodeRelationshipProps) => {
  const { "*": branchName } = useParams();

  const AddedCount = relationship.elements.filter(({ status }) => status === "ADDED").length;
  const RemovedCount = relationship.elements.filter(({ status }) => status === "REMOVED").length;
  const UpdatedCount = relationship.elements.filter(({ status }) => status === "UPDATED").length;
  return (
    <DiffRow
      status={status}
      hasConflicts={relationship.contains_conflict}
      title={
        <div className="flex items-center justify-between pr-2">
          <div className="py-2 font-semibold">{relationship.label}</div>

          {!branchName && relationship.path_identifier && (
            <DiffThread path={relationship.path_identifier} />
          )}
        </div>
      }
      right={
        <div className="space-x-1">
          {AddedCount > 0 && (
            <Badge variant="green" className="gap-1 font-medium">
              <Icon icon="mdi:plus-circle-outline" />
              {AddedCount}
            </Badge>
          )}
          {UpdatedCount > 0 && (
            <Badge variant="blue" className="gap-1 font-medium">
              <Icon icon="mdi:plus-circle-outline" />
              {UpdatedCount}
            </Badge>
          )}
          {RemovedCount > 0 && (
            <Badge variant="red" className="gap-1 font-medium">
              <Icon icon="mdi:minus-circle-outline" />
              {RemovedCount}
            </Badge>
          )}
        </div>
      }
    >
      <div className="divide-y divide-gray-200 border-gray-200 border-t">
        {relationship.elements.map((element, index: number) => (
          <DiffNodeRelationshipElement key={index} element={element} status={status} />
        ))}
      </div>
    </DiffRow>
  );
};
