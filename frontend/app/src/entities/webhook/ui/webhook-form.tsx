import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { IP_PREFIX_POOL } from "@/entities/resource-manager/constants";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useMemo } from "react";
import { toast } from "react-toastify";

export interface WebhookFormProps extends NodeFormProps {
  kind: string;
}

export function WebhookForm({
  kind,
  currentObject,
  isUpdate,
  onSuccess,
  onSubmit,
  ...props
}: WebhookFormProps) {
  const { schema: genericPrefixSchema } = useSchema(kind);
  const { currentBranch } = useCurrentBranch();

  const fields = useMemo(() => {
    return getFormFieldsFromSchema({
      ...props,
      initialObject: currentObject,
      isUpdate,
    });
  }, [props, genericPrefixSchema, currentObject, isUpdate]);

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString =
        isUpdate && currentObject
          ? updateObjectWithId({
              kind,
              data: stringifyWithoutQuotes({
                id: currentObject.id,
                ...newObject,
              }),
            })
          : createObject({
              kind,
              data: stringifyWithoutQuotes(newObject),
            });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: currentBranch.name,
        },
      });

      const operationType = isUpdate ? "Update" : "Create";
      const successMessage = isUpdate ? "Webhook updated" : "Webhook created";
      toast(<Alert type={ALERT_TYPES.SUCCESS} message={successMessage} />, {
        toastId: `alert-success-webhook-${operationType}`,
      });

      if (onSuccess) {
        const resultData = result?.data?.[`${IP_PREFIX_POOL}${operationType}`];
        await onSuccess(resultData);
      }
    } catch (error: unknown) {
      console.error(
        `An error occurred while ${isUpdate ? "updating" : "creating"} the Webhook:`,
        error
      );
    }
  }

  return (
    <DynamicForm
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields }) : handleSubmit(formData)
      }
      className="p-4 overflow-auto"
    />
  );
}
