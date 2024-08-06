import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { iNodeSchema, IProfileSchema } from "@/state/atoms/schema.atom";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import useFilters from "@/hooks/useFilters";
import { useAuth } from "@/hooks/useAuth";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { CREATE_ACCOUNT_TOKEN } from "@/graphql/mutations/accounts/createAccountToken";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import DynamicForm from "@/components/form/dynamic-form";
import { classNames } from "@/utils/common";
import { ProfileData } from "@/components/form/object-form";

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles: Array<ProfileData>;
};

export type NodeFormProps = {
  operation?: "create" | "update";
  className?: string;
  schema: iNodeSchema | IProfileSchema;
  profiles?: ProfileData[];
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
};

export const NodeForm = ({
  className,
  currentObject,
  schema,
  profiles = [],
  onSuccess,
  isFilterForm,
  onSubmit,
  ...props
}: NodeFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [filters] = useFilters();
  const auth = useAuth();

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    auth,
    isFilterForm,
    filters,
  });

  async function onSubmitCreate(data: Record<string, FormFieldValue>) {
    try {
      if (schema.kind === ACCOUNT_TOKEN_OBJECT) {
        const result = await graphqlClient.mutate({
          mutation: CREATE_ACCOUNT_TOKEN,
          variables: {
            name: data.name.value,
          },
          context: {
            branch: branch?.name,
            date,
          },
        });

        toast(() => <Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.label} created`} />, {
          toastId: `alert-success-${schema?.name}-created`,
        });

        if (onSuccess) await onSuccess(result?.data?.[`${schema?.kind}Create`]);
        return;
      }

      const newObject = getCreateMutationFromFormData(fields, data);

      if (!Object.keys(newObject).length) {
        return;
      }

      const profileIds = profiles?.map((profile) => ({ id: profile.id })) ?? [];

      const mutationString = createObject({
        kind: schema?.kind,
        data: stringifyWithoutQuotes({
          ...newObject,
          ...(profileIds.length ? { profiles: profileIds } : {}),
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

      toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} created`} />, {
        toastId: `alert-success-${schema?.name}-created`,
      });

      if (onSuccess) await onSuccess(result?.data?.[`${schema?.kind}Create`]);
    } catch (error: unknown) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <DynamicForm
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields, profiles }) : onSubmitCreate(formData)
      }
      className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4", className)}
      {...props}
    />
  );
};
