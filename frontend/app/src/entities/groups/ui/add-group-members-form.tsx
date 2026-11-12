import { Button } from "@infrahub/ui";
import { toast } from "react-toastify";

import { Row } from "@/shared/components/container";
import { DEFAULT_FORM_FIELD_VALUE } from "@/shared/components/form/constants";
import { GenericRelationshipField } from "@/shared/components/form/fields/relationships/generic-relationship.field";
import type { FormRelationshipValue } from "@/shared/components/form/type";
import { isRequired } from "@/shared/components/form/utils/validation";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { Form, FormSubmit } from "@/shared/components/ui/form";
import { pluralize } from "@/shared/utils/string";

import { GROUP_MEMBERS_RELATIONSHIP } from "@/entities/groups/domain/model/group";
import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import type { RelationshipSchema } from "@/entities/schema/domain/model/schema";

interface AddGroupMembersFormProps {
  groupId: string;
  membersRelationship: RelationshipSchema;
  onSuccess: () => void;
  onCancel: () => void;
}

type AddGroupMembersFormValues = {
  [GROUP_MEMBERS_RELATIONSHIP]: FormRelationshipValue;
};

export function AddGroupMembersForm({
  groupId,
  membersRelationship,
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

    toast(
      <Alert type={ALERT_TYPES.SUCCESS} message={`${pluralize(value.length, "member")} added`} />
    );

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
        label={membersRelationship.label ?? "Members"}
        relationship={membersRelationship}
        rules={{ validate: isRequired }}
      />

      <Row className="justify-end">
        <Button variant="outline" onPress={onCancel}>
          Cancel
        </Button>

        <FormSubmit>Save</FormSubmit>
      </Row>
    </Form>
  );
}
