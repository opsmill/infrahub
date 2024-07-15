import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { iNodeSchema } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import getMutationMetaDetailsFromFormData from "@/utils/getMutationMetaDetailsFromFormData";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { toast } from "react-toastify";
import DynamicForm from "@/components/form/dynamic-form";
interface Props {
  row: any;
  schema: iNodeSchema;
  type: "attribute" | "relationship";
  attributeOrRelationshipToEdit: any;
  attributeOrRelationshipName: any;
  closeDrawer: () => void;
  onUpdateComplete: () => void;
}

export default function ObjectItemMetaEdit(props: Props) {
  const {
    row,
    type,
    attributeOrRelationshipName,
    schema,
    attributeOrRelationshipToEdit,
    onUpdateComplete,
    closeDrawer,
  } = props;

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  async function onSubmit(data: any) {
    const updatedObject = getMutationMetaDetailsFromFormData(
      schema,
      data,
      row,
      type,
      attributeOrRelationshipName,
      attributeOrRelationshipToEdit
    );

    if (Object.keys(updatedObject).length) {
      try {
        const mutationString = updateObjectWithId({
          kind: schema.kind,
          data: stringifyWithoutQuotes(updatedObject),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });

        toast(() => <Alert type={ALERT_TYPES.SUCCESS} message={"Metadata updated"} />);

        onUpdateComplete();

        closeDrawer();
      } catch (e) {
        console.error("Something went wrong while updating the meetadata", e);
        return;
      }
    }
  }

  return (
    <div className="flex-1 bg-custom-white flex">
      <DynamicForm
        fields={[
          {
            name: "owner",
            label: "Owner",
            type: "relationship",
            relationship: { cardinality: "one", inherited: true, peer: "LineageOwner" } as any,
            schema,
            defaultValue: attributeOrRelationshipToEdit.owner?.id,
            parent: attributeOrRelationshipToEdit.owner?.__typename,
          },
          {
            name: "source",
            label: "Source",
            type: "relationship",
            relationship: { cardinality: "one", inherited: true, peer: "LineageSource" } as any,
            schema,
            defaultValue: attributeOrRelationshipToEdit.source?.id,
            parent: attributeOrRelationshipToEdit.source?.__typename,
          },
          {
            name: "is_visible",
            label: "is visible",
            type: "Checkbox",
            defaultValue: attributeOrRelationshipToEdit.is_visible,
            rules: {
              required: true,
            },
          },
          {
            name: "is_protected",
            label: "is protected",
            type: "Checkbox",
            defaultValue: attributeOrRelationshipToEdit.is_protected,
            rules: {
              required: true,
            },
          },
        ]}
        onCancel={closeDrawer}
        onSubmit={async (data: any) => {
          await onSubmit(data);
        }}
        className="w-full p-4"
      />
    </div>
  );
}
