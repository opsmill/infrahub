import { toast } from "react-toastify";

import NoDataFound from "@/shared/components/errors/no-data-found";
import DynamicForm, { type DynamicFormProps } from "@/shared/components/form/dynamic-form";
import type {
  FormRelationshipValue,
  RelationshipManyValueFromUser,
} from "@/shared/components/form/type";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { pluralize } from "@/shared/utils/string";

import { useAddRelationships } from "@/entities/nodes/relationships/ui/queries/add-relationships.mutation";
import type { ModelSchema } from "@/entities/schema/types";

interface AddGroupFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  objectId: string;
  defaultGroupIds?: FormRelationshipValue;
  schema: ModelSchema;
  onUpdateCompleted?: () => void;
}

export function AddGroupForm({
  objectId,
  onUpdateCompleted,
  defaultGroupIds,
  schema,
  ...props
}: AddGroupFormProps) {
  const { mutateAsync: addRelationships } = useAddRelationships();

  const memberOfGroupsRelationship = schema.relationships?.find(
    ({ name }) => name === "member_of_groups"
  );

  if (!memberOfGroupsRelationship) {
    return <NoDataFound message={`Model ${schema.kind} has no relationship with any group`} />;
  }

  async function onSubmit(groupIds: Array<{ id: string }>) {
    try {
      await addRelationships({
        objectId,
        relationshipName: "member_of_groups",
        relationshipIds: groupIds.map(({ id }) => id),
      });

      toast(
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`${pluralize(groupIds.length, "group")} added`}
        />
      );

      if (onUpdateCompleted) onUpdateCompleted();
    } catch (e) {
      console.error("Something went wrong while adding object to groups:", e);
    }
  }

  return (
    <DynamicForm
      fields={[
        {
          label: "Add groups",
          name: "groupIds",
          type: "relationship",
          rules: { required: true },
          defaultValue: defaultGroupIds,
          relationship: memberOfGroupsRelationship,
        },
      ]}
      onSubmit={async (formData) => {
        const { groupIds } = formData as { groupIds: RelationshipManyValueFromUser };

        if (!groupIds.value) return;
        await onSubmit(groupIds.value.map(({ id }) => ({ id })));
      }}
      {...props}
    />
  );
}
