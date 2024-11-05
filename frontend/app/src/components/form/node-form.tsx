import DynamicForm from "@/components/form/dynamic-form";
import { ProfileData } from "@/components/form/object-form";
import { DynamicFieldProps, FormFieldValue, NumberPoolData } from "@/components/form/type";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { CoreNumberPool } from "@/generated/graphql";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { CREATE_ACCOUNT_TOKEN } from "@/graphql/mutations/accounts/createAccountToken";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { GET_FORM_REQUIREMENTS } from "@/graphql/queries/forms/getFormRequirements";
import { useAuth } from "@/hooks/useAuth";
import useFilters from "@/hooks/useFilters";
import useQuery from "@/hooks/useQuery";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { NUMBER_POOL_KIND } from "@/screens/resource-manager/constants";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { IProfileSchema, iNodeSchema } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { stringifyWithoutQuotes } from "@/utils/string";
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
