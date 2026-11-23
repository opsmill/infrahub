import ObjectForm from "@/shared/components/form/object-form";
import { FormContext } from "@/shared/components/form/utils/form-context";

import { GROUP_GENERIC, GROUP_MEMBERS_RELATIONSHIP } from "@/entities/groups/domain/model/group";
import { AddGroupMembersForm } from "@/entities/groups/ui/add-group-members-form";
import type { NodeObject } from "@/entities/nodes/object/domain/model/node";
import { SelectPeerForm } from "@/entities/nodes/object/ui/object-details/action-buttons/select-peer-form";
import type { ModelSchema, RelationshipSchema } from "@/entities/schema/domain/model/schema";
import { isOfKind } from "@/entities/schema/domain/rules/is-of-kind";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface AddRelationshipFormProps {
  objectData: NodeObject;
  objectSchema: ModelSchema;
  relationshipSchema: RelationshipSchema;
  onSuccess: () => Promise<void>;
  onCancel: () => void;
}

export function AddRelationshipForm(props: AddRelationshipFormProps) {
  return (
    <FormContext value={{ parentSchema: props.objectSchema, parentData: props.objectData }}>
      <AddRelationshipFormContent {...props} />
    </FormContext>
  );
}

function AddRelationshipFormContent({
  objectData,
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
        groupId={objectData.id}
        membersRelationshipSchema={relationshipSchema}
        onSuccess={onSuccess}
        onCancel={onCancel}
      />
    );
  }

  return (
    <SelectPeerForm
      objectId={objectData.id}
      relationshipSchema={relationshipSchema}
      onSuccess={onSuccess}
      onCancel={onCancel}
    />
  );
}
