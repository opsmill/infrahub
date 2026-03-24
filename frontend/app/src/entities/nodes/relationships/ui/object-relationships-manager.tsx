import { Navigate } from "react-router";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { RelationshipsButtons } from "@/entities/nodes/object-item-details/action-buttons/relationships-buttons";
import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import type { NodeObject } from "@/entities/nodes/types";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export interface ObjectRelationshipsManagerProps {
  parentNodeSchema: ModelSchema;
  parentNodeData: NodeObject;
  relationshipName: string;
  permission: Permission;
}

export function ObjectRelationshipsManager({
  parentNodeSchema,
  parentNodeData,
  relationshipName,
  permission,
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
    return <Navigate to={getObjectDetailsUrl(parentNodeData.__typename, parentNodeData.id)} />;
  }

  return (
    <ObjectTableProvider schema={relationshipSchema}>
      <Row className="justify-end p-2">
        <RelationshipsButtons
          permission={permission}
          schema={parentNodeSchema}
          objectDetailsData={parentNodeData}
        />
      </Row>
      <RelationshipTable
        parentKind={parentNodeSchema.kind!}
        parentId={parentNodeData.id}
        relationshipName={relationshipName}
        relationshipSchema={relationshipSchema}
      />
    </ObjectTableProvider>
  );
}
