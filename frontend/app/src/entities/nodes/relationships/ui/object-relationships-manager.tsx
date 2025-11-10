import { Navigate } from "react-router";
import { toast } from "react-toastify";

import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ObjectRelationshipsManagerProps {
  parentNodeSchema: ModelSchema;
  parentNodeId: string;
  relationshipName: string;
}
export function ObjectRelationshipsManager({
  parentNodeSchema,
  parentNodeId,
  relationshipName,
}: ObjectRelationshipsManagerProps) {
  const relationshipDefinition = parentNodeSchema.relationships?.find(
    (r) => r?.name === relationshipName
  );
  const { schema: relationshipSchema } = useSchema(relationshipDefinition?.peer);

  if (!relationshipSchema) {
    toast(
      <Alert
        type={ALERT_TYPES.ERROR}
        message={
          <>
            Relationship <strong>{relationshipName}</strong> not found in {parentNodeSchema.label}{" "}
            schema
          </>
        }
      />
    );
    return <Navigate to={getObjectDetailsUrl(parentNodeSchema.kind as string, parentNodeId)} />;
  }

  return (
    <ObjectTableProvider schema={relationshipSchema}>
      <RelationshipTable
        parentKind={parentNodeSchema.kind as string}
        parentId={parentNodeId}
        relationshipName={relationshipName}
        relationshipSchema={relationshipSchema}
      />
    </ObjectTableProvider>
  );
}
