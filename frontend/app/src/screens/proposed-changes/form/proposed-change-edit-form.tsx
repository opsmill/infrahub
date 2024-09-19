import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { useAtomValue } from "jotai/index";
import { schemaState } from "@/state/atoms/schema.atom";
import { branchesState, currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { ACCOUNT_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { getUpdateMutationFromFormData } from "@/components/form/utils/mutations/getUpdateMutationFromFormData";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import DynamicForm from "@/components/form/dynamic-form";

type ProposedChangeEditFormProps = {
  initialData: Record<string, AttributeType>;
  onSuccess?: () => void;
};

export const ProposedChangeEditForm = ({ initialData, onSuccess }: ProposedChangeEditFormProps) => {
  const nodes = useAtomValue(schemaState);
  const branches = useAtomValue(branchesState);
  const currentBranch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const proposedChangeSchema = nodes.find(({ kind }) => kind === PROPOSED_CHANGES_OBJECT);

  if (!proposedChangeSchema) return null;

  const fields: Array<DynamicFieldProps> = [
    {
      name: "name",
      type: "Text",
      label: "Name",
      defaultValue: { source: { type: "user" }, value: initialData?.name?.value },
      rules: {
        validate: {
          required: ({ value }: FormFieldValue) => {
            return (value !== null && value !== undefined && value !== "") || "Required";
          },
        },
      },
    },
    {
      name: "description",
      type: "TextArea",
      label: "Description",
      defaultValue: { source: { type: "user" }, value: initialData?.description?.value },
    },
    {
      name: "source_branch",
      type: "enum",
      label: "Source Branch",
      defaultValue: { source: { type: "user" }, value: initialData?.source_branch?.value },
      items: branches.map(({ id, name }) => ({ id, name })),
      rules: {
        validate: {
          required: ({ value }: FormFieldValue) => {
            return (value !== null && value !== undefined) || "Required";
          },
        },
      },
      disabled: true,
    },
    {
      name: "destination_branch",
      type: "enum",
      label: "Destination Branch",
      defaultValue: { source: { type: "user" }, value: initialData?.destination_branch?.value },
      items: branches.map(({ id, name }) => ({ id, name })),
      disabled: true,
    },
    {
      name: "reviewers",
      label: "Reviewers",
      type: "relationship",
      relationship: { cardinality: "many", peer: ACCOUNT_OBJECT } as any,
      schema: {} as any,
      defaultValue: {
        source: { type: "user" },
        value:
          initialData?.reviewers?.edges
            .map((edge: any) => ({ id: edge?.node?.id }))
            .filter(Boolean) ?? [],
      },
      options: initialData?.reviewers?.edges.map(({ node }) => ({
        id: node?.id,
        name: node?.display_label,
      })),
    },
  ];

  async function onSubmit(formData: any) {
    const updatedObject = getUpdateMutationFromFormData({ formData, fields });

    if (Object.keys(updatedObject).length) {
      try {
        const mutationString = updateObjectWithId({
          kind: proposedChangeSchema?.kind,
          data: stringifyWithoutQuotes({
            id: initialData.id,
            ...updatedObject,
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: currentBranch?.name, date },
        });

        toast(
          () => (
            <Alert type={ALERT_TYPES.SUCCESS} message={`${proposedChangeSchema?.name} updated`} />
          ),
          {
            toastId: "alert-success-updated",
          }
        );

        if (onSuccess) onSuccess();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }
    }
  }

  return <DynamicForm onSubmit={onSubmit} fields={fields} className="p-4" />;
};
