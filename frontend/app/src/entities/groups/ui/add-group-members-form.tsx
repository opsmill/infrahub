import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { GenericRelationshipField } from "@/shared/components/form/fields/relationships/generic-relationship.field";
import type { FormRelationshipValue } from "@/shared/components/form/type";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormActions, FormSubmit } from "@/shared/components/ui/form";

import { GROUP_MEMBERS_RELATIONSHIP } from "@/entities/groups/domain/model/group";
import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";

interface AddGroupMembersFormProps {
  groupId: string;
  membersRelationshipSchema: RelationshipSchema;
  onSuccess: () => void;
  onCancel: () => void;
}

type AddGroupMembersFormValues = {
  [GROUP_MEMBERS_RELATIONSHIP]: FormRelationshipValue;
};

export function AddGroupMembersForm({
  groupId,
  membersRelationshipSchema,
  onSuccess,
  onCancel,
}: AddGroupMembersFormProps) {
  const { mutateAsync: addRelationships } = useAddRelationships();

  const handleSubmit = async (formData: AddGroupMembersFormValues) => {
    const { value } = formData[GROUP_MEMBERS_RELATIONSHIP];
    if (!Array.isArray(value) || value.length === 0) return;

    await addRelationships({
      objectId: groupId,
      relationshipName: GROUP_MEMBERS_RELATIONSHIP,
      relationshipIds: value.map(({ id }) => id),
    });

    // The backend skips nodes that are already members, so the number selected can exceed the number added.
    toast(<Alert type={ALERT_TYPES.SUCCESS} message="Members added" />);

    onSuccess();
  };

  return (
    <Form<AddGroupMembersFormValues>
      onSubmit={handleSubmit}
      onCancel={onCancel}
      defaultValues={{ [GROUP_MEMBERS_RELATIONSHIP]: DEFAULT_FORM_FIELD_VALUE }}
    >
      <GenericRelationshipField
        type="relationship"
        name={GROUP_MEMBERS_RELATIONSHIP}
        label={membersRelationshipSchema.label ?? "Members"}
        relationship={membersRelationshipSchema}
        rules={{ validate: isRequired }}
      />

      <FormActions>
        <Button variant="outline" onPress={onCancel}>
          Cancel
        </Button>

        <FormSubmit>Save</FormSubmit>
      </FormActions>
    </Form>
  );
}
