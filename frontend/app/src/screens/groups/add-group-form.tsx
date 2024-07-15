import DynamicForm, { DynamicFormProps } from "@/components/form/dynamic-form";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import NoDataFound from "@/screens/errors/no-data-found";
import { useMutation } from "@apollo/client";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { pluralize } from "@/utils/string";
import { ADD_RELATIONSHIP } from "@/graphql/mutations/relationships/addRelationship";

interface AddGroupFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  objectId: string;
  schema: iNodeSchema;
  onUpdateCompleted?: () => void;
}

export default function AddGroupForm({
  objectId,
  onUpdateCompleted,
  schema,
  ...props
}: AddGroupFormProps) {
  const [addObjectToGroups] = useMutation(ADD_RELATIONSHIP, {
    variables: { relationshipName: "member_of_groups" },
  });

  const memberOfGroupsRelationship = schema.relationships?.find(
    ({ name }) => name === "member_of_groups"
  );

  if (!memberOfGroupsRelationship) {
    return <NoDataFound message={`Model ${schema.kind} has no relationship with any group`} />;
  }

  async function onSubmit({ groupIds }: { groupIds: Array<{ id: string }> }) {
    try {
      await addObjectToGroups({ variables: { objectId, relationshipIds: groupIds } });

      toast(() => (
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`${pluralize(groupIds.length, "group")} added`}
        />
      ));

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
          relationship: memberOfGroupsRelationship,
          schema,
        },
      ]}
      onSubmit={onSubmit}
      {...props}
    />
  );
}
