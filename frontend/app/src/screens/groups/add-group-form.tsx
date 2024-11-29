import DynamicForm, { DynamicFormProps } from "@/components/form/dynamic-form";
import { FormRelationshipValue, RelationshipManyValueFromUser } from "@/components/form/type";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { updateGroupsQuery } from "@/graphql/mutations/groups/updateGroupsQuery";
import { useMutation } from "@/hooks/useQuery";
import NoDataFound from "@/screens/errors/no-data-found";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import { pluralize } from "@/utils/string";
import { toast } from "react-toastify";

interface AddGroupFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  objectId: string;
  defaultGroupIds?: FormRelationshipValue;
  schema: iNodeSchema;
  onUpdateCompleted?: () => void;
}

export default function AddGroupForm({
  objectId,
  onUpdateCompleted,
  defaultGroupIds,
  schema,
  ...props
}: AddGroupFormProps) {
  const [addObjectToGroups] = useMutation(updateGroupsQuery({ schema, objectId }));

  const memberOfGroupsRelationship = schema.relationships?.find(
    ({ name }) => name === "member_of_groups"
  );

  if (!memberOfGroupsRelationship) {
    return <NoDataFound message={`Model ${schema.kind} has no relationship with any group`} />;
  }

  async function onSubmit(groupIds: Array<{ id: string }>) {
    try {
      await addObjectToGroups({ variables: { id: objectId, groupIds } });

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
          schema,
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
