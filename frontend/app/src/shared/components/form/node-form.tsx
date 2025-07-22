import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { useAuth } from "@/entities/authentication/ui/useAuth";
import { currentBranchAtom } from "@/entities/branches/stores";
import { createObject } from "@/entities/nodes/api/createObject";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/domain/get-number-pools.query";
import { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { CREATE_ACCOUNT_TOKEN } from "@/entities/user-profile/api/createAccountToken";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { classNames } from "@/shared/utils/common";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { toast } from "react-toastify";
import { LoadingIndicator } from "../loading/loading-indicator";

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles?: Array<ProfileData>;
};

export type NodeFormProps = {
  className?: string;
  schema: NodeSchema | ProfileSchema;
  profiles?: ProfileData[];
  currentObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  isFilterForm?: boolean;
  isUpdate?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
  onSuccess?: (newObject: any) => void;
  onCancel?: () => void;
};

export const NodeForm = ({
  className,
  currentObject,
  objectTemplate,
  schema,
  profiles,
  onSuccess,
  isFilterForm,
  onSubmit,
  isUpdate,
  ...props
}: NodeFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const auth = useAuth();

  const { data: numberPools, isPending } = useGetNumberPools({
    objectKinds: [schema.kind as string, ...(schema.inherit_from ?? [])],
  });

  if (isPending) return <LoadingIndicator className="mt-4" />;

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    objectTemplate,
    auth,
    isFilterForm,
    pools: numberPools,
    isUpdate,
  });

  async function onSubmitCreate(data: Record<string, FormFieldValue>) {
    try {
      if (schema.kind === ACCOUNT_TOKEN_OBJECT) {
        const result = await graphqlClient.mutate({
          mutation: CREATE_ACCOUNT_TOKEN,
          variables: {
            name: data.name?.value,
            expiration: data.expiration?.value,
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

      const newObject = getCreateMutationFromFormData(fields, data, objectTemplate?.id);
      const isObjectEmpty = Object.keys(newObject).length === 0;
      const isProfilesEmpty = !profiles || profiles.length === 0;

      if (isObjectEmpty && isProfilesEmpty) {
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
      className={classNames("bg-white flex flex-col flex-1 overflow-auto p-4", className)}
      {...props}
    />
  );
};
