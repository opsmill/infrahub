import {
  genericsState,
  iNodeSchema,
  IProfileSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import { useEffect, useState } from "react";
import { tComboboxItem } from "@/components/ui/combobox";
import NoDataFound from "@/screens/errors/no-data-found";
import { gql } from "@apollo/client";
import { createObject } from "@/graphql/mutations/objects/createObject";
import { stringifyWithoutQuotes } from "@/utils/string";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { toast } from "react-toastify";
import { Alert, ALERT_TYPES } from "@/components/ui/alert";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import { classNames } from "@/utils/common";
import DynamicForm, { DynamicFormProps } from "@/components/form/dynamic-form";
import { AttributeType, RelationshipType } from "@/utils/getObjectItemDisplayValue";
import { useAuth } from "@/hooks/useAuth";
import useFilters from "@/hooks/useFilters";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { CREATE_ACCOUNT_TOKEN } from "@/graphql/mutations/accounts/createAccountToken";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { ProfilesSelector } from "@/components/form/profiles-selector";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";
import { GenericSelector } from "@/components/form/generic-selector";
import { useSchema } from "@/hooks/useSchema";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
  __typename: string;
};

interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  currentProfiles?: ProfileData[];
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
}

const ObjectForm = ({ kind, isFilterForm, ...props }: ObjectFormProps) => {
  const nodeSchemas = useAtomValue(schemaState);
  const profileSchemas = useAtomValue(profilesAtom);
  const { schema, isGeneric } = useSchema(kind);
  const [kindToCreate, setKindToCreate] = useState<string>();

  useEffect(() => {
    if (isGeneric && schema.used_by?.length === 1) {
      setKindToCreate(schema.used_by[0]);
    }
  }, [schema?.kind]);

  if (!schema) {
    return (
      <NoDataFound
        message={`Unable to generate the form. We couldn't find a schema for the kind "${kind}". Please check if the kind is correct or contact support if this issue persists.`}
      />
    );
  }

  if (isFilterForm) {
    return <NodeForm schema={schema} {...props} />;
  }

  if (isGeneric) {
    if (!schema.used_by || schema.used_by?.length === 0) {
      return (
        <NoDataFound message="This generic schema is not currently associated with any nodes. To create an instance, you need to first link this generic to at least one node type. Please check your schema configuration." />
      );
    }

    const items: Array<tComboboxItem> = schema.used_by
      .map((kind) => {
        const relatedSchema = [...nodeSchemas, ...profileSchemas].find(
          (schema) => schema.kind === kind
        );

        if (!relatedSchema) return null;

        return {
          value: relatedSchema.kind,
          label: relatedSchema.label ?? relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      })
      .filter((item) => !!item);

    return (
      <>
        <GenericSelector items={items} value={kindToCreate} onChange={setKindToCreate} />
        {kindToCreate && <NodeWithProfileForm kind={kindToCreate} {...props} />}
      </>
    );
  }

  return <NodeWithProfileForm kind={kind} isFilterForm={isFilterForm} {...props} />;
};

const NodeWithProfileForm = ({
  isFilterForm,
  kind,
  currentProfiles,
  ...props
}: ObjectFormProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const [selectedProfiles, setSelectedProfiles] = useState<ProfileData[] | undefined>();

  const nodeSchema = [...nodes, ...generics, ...profiles].find((node) => node.kind === kind);

  if (!nodeSchema) {
    return <NoDataFound message={`${kind} schema not found. Try to reload the page.`} />;
  }

  return (
    <>
      {!isFilterForm && "generate_profile" in nodeSchema && nodeSchema.generate_profile && (
        <ProfilesSelector
          schema={nodeSchema}
          defaultValue={currentProfiles}
          value={selectedProfiles}
          onChange={setSelectedProfiles}
          currentProfiles={currentProfiles}
        />
      )}
      <NodeForm
        schema={nodeSchema}
        isFilterForm={isFilterForm}
        profiles={selectedProfiles}
        {...props}
      />
    </>
  );
};

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles: Array<ProfileData>;
};

type NodeFormProps = {
  operation?: "create" | "update";
  className?: string;
  schema: iNodeSchema | IProfileSchema;
  profiles?: ProfileData[];
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType | RelationshipType>;
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
};

const NodeForm = ({
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

export default ObjectForm;
