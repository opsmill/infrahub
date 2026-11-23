import ObjectForm from "@/shared/components/form/object-form";

import { GROUP_GENERIC, GROUP_MEMBERS_RELATIONSHIP } from "@/entities/groups/domain/model/group";
import { AddGroupMembersForm } from "@/entities/groups/ui/add-group-members-form";
import { SelectPeerForm } from "@/entities/nodes/object/ui/object-details/action-buttons/select-peer-form";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AddRelationshipFormProps {
  objectId: string;
  objectSchema: ModelSchema;
  relationshipSchema: RelationshipSchema;
  onSuccess: () => Promise<void>;
  onCancel: () => void;
}

export function AddRelationshipForm({
  objectId,
  objectSchema,
  relationshipSchema,
  onSuccess,
  onCancel,
}: AddRelationshipFormProps) {
  const peerSchema = useSchema(relationshipSchema.peer);
  const peerParentRelationship = peerSchema.schema?.relationships?.find(
    (r) => r.kind === "Parent" && !r.optional && isOfKind(r.peer, objectSchema)
  );

  if (
    relationshipSchema.kind === "Component" &&
    peerParentRelationship &&
    relationshipSchema.peer
  ) {
    return <ObjectForm kind={relationshipSchema.peer} onSuccess={onSuccess} onCancel={onCancel} />;
  }

  if (
    isOfKind(GROUP_GENERIC, objectSchema) &&
    relationshipSchema.name === GROUP_MEMBERS_RELATIONSHIP
  ) {
    return (
      <AddGroupMembersForm
        groupId={objectId}
        membersRelationshipSchema={relationshipSchema}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );
  }

  return (
    <SelectPeerForm
      objectId={objectId}
      relationshipSchema={relationshipSchema}
      onSuccess={onSuccess}
      onCancel={onCancel}
    />
  );
}
