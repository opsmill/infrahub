import { currentBranchAtom } from "@/entities/branches/stores";
import { createObject } from "@/entities/nodes/api/createObject";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import { NODE_TRIGGER_RULE } from "@/entities/triggers/constants";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { NodeFormProps } from "@/shared/components/form/node-form";
import { FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { useMemo } from "react";
import { toast } from "react-toastify";

interface NumberPoolFormProps extends NodeFormProps {}

export const NodeTriggerRuleForm = ({
  currentObject,
  isUpdate,
  onSubmit,
  onSuccess,
  ...props
}: NumberPoolFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

  const fields = useMemo(() => {
    const schemaFields = getFormFieldsFromSchema({
      ...props,
      initialObject: currentObject,
      isUpdate,
    });

    // Replace default_address_type (text) field with a select
    return schemaFields.map((field) => {
      if (field.name === "node_kind") {
        return {
          ...field,
          type: "kind",
        };
      }

      return field;
    });
  }, [props.schema.kind, currentObject, isUpdate]);

  async function handleSubmit(data: Record<string, FormFieldValue>) {
    try {
      const newObject = getCreateMutationFromFormData(fields, data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = currentObject
        ? updateObjectWithId({
            kind: NODE_TRIGGER_RULE,
            data: stringifyWithoutQuotes({
              id: currentObject.id,
              ...newObject,
            }),
          })
        : createObject({
            kind: NODE_TRIGGER_RULE,
            data: stringifyWithoutQuotes({
              ...newObject,
            }),
          });

      const mutation = gql`
        ${mutationString}
      `;

      const result = await graphqlClient.mutate({
        mutation,
        context: {
          branch: branch?.name,
          date,
        },
      });

      if (currentObject) {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node trigger rule updated!"} />, {
          toastId: "alert-success-node-trigger-rule-updated",
        });
      } else {
        toast(<Alert type={ALERT_TYPES.SUCCESS} message={"Node trigger rule created!"} />, {
          toastId: "alert-success-node-trigger-rule-created",
        });
      }

      if (onSuccess) await onSuccess(result?.data?.[`${NODE_TRIGGER_RULE}Create`]);
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return <DynamicForm fields={fields} onSubmit={handleSubmit} className="p-4 overflow-auto" />;
};
