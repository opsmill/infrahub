import { Navigate } from "react-router";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { RelationshipsButtons } from "@/entities/nodes/object/ui/object-details/action-buttons/relationships-buttons";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import type { Permission } from "@/entities/permission/domain/model/permission";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
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
          relationshipName={relationshipName}
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
