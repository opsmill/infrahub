import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { useAuth } from "@/entities/authentication/useAuth";
import { currentBranchAtom } from "@/entities/branches/branches.atom";
import { createObject } from "@/entities/nodes/api/createObject";
import { GET_FORM_REQUIREMENTS } from "@/entities/nodes/api/getFormRequirements";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { NUMBER_POOL_KIND } from "@/entities/resource-manager/constants";
import { IProfileSchema, iNodeSchema } from "@/entities/schema/schema.atom";
import { CREATE_ACCOUNT_TOKEN } from "@/entities/user-profile/api/createAccountToken";
import { CoreNumberPool } from "@/shared/api/graphql/generated/graphql";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps, FormFieldValue, NumberPoolData } from "@/shared/components/form/type";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import LoadingScreen from "@/shared/components/loading-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import useFilters from "@/shared/hooks/useFilters";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { classNames } from "@/shared/utils/common";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { toast } from "react-toastify";

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles?: Array<ProfileData>;
};

export type NodeFormProps = {
  className?: string;
  schema: iNodeSchema | IProfileSchema;
  profiles?: ProfileData[];
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  isFilterForm?: boolean;
  isUpdate?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
};

export const NodeForm = ({
  className,
  currentObject,
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
  const [filters] = useFilters();
  const auth = useAuth();

  const { data, loading } = useQuery(GET_FORM_REQUIREMENTS, { variables: { kind: schema.kind } });

  if (loading) return <LoadingScreen hideText className="mt-4" />;

  const numberPools: Array<NumberPoolData> = data?.[NUMBER_POOL_KIND].edges.map(
    ({ node }: { node: CoreNumberPool }): NumberPoolData => ({
      id: node.id,
      label: node.display_label as string,
      kind: node.__typename as string,
      nodeAttribute: {
        id: node.node_attribute.id as string,
        name: node.node_attribute.value as string,
      },
    })
  );

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    auth,
    isFilterForm,
    filters,
    pools: numberPools,
    isUpdate,
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
      className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4", className)}
      {...props}
    />
  );
};
