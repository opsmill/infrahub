import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { ACCOUNT_GENERIC_OBJECT, PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { branchesState } from "@/entities/branches/stores";
import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { AttributeType } from "@/entities/nodes/getObjectItemDisplayValue";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { nodeSchemasAtom } from "@/entities/schema/stores/schema.atom";

type ProposedChangeEditFormProps = {
  initialData: Record<string, AttributeType>;
  onSuccess?: () => void;
};

export const ProposedChangeEditForm = ({ initialData, onSuccess }: ProposedChangeEditFormProps) => {
  const nodes = useAtomValue(nodeSchemasAtom);
  const branches = useAtomValue(branchesState);
  const { currentBranch } = useCurrentBranch();
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
      relationship: { cardinality: "many", peer: ACCOUNT_GENERIC_OBJECT } as any,
      defaultValue: {
        source: { type: "user" },
        value:
          initialData?.reviewers?.edges
            .map((edge: any) => ({
              id: edge?.node?.id,
              display_label: edge?.node ? getNodeLabel(edge.node) : undefined,
              __typename: edge?.node?.__typename,
            }))
            .filter(Boolean) ?? [],
      },
      options: initialData?.reviewers?.edges.map(({ node }) => ({
        id: node?.id,
        name: node ? getNodeLabel(node) : undefined,
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
          context: { branch: currentBranch.name, date },
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

  return <DynamicForm onSubmit={onSubmit} fields={fields} className="overflow-auto p-4" />;
};
