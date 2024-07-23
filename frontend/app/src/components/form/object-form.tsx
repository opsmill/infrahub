import {
  genericsState,
  iNodeSchema,
  IProfileSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import { useId, useState } from "react";
import { Combobox, tComboboxItem } from "@/components/ui/combobox";
import NoDataFound from "@/screens/errors/no-data-found";
import Label from "@/components/ui/label";
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
import { AttributeType } from "@/utils/getObjectItemDisplayValue";
import { useAuth } from "@/hooks/useAuth";
import useFilters from "@/hooks/useFilters";
import { ACCOUNT_TOKEN_OBJECT } from "@/config/constants";
import { createToken } from "@/graphql/mutations/accounts/createToken";
import { getFormFieldsFromSchema } from "@/components/form/utils/getFormFieldsFromSchema";
import { ProfilesSelector } from "@/components/form/profiles-selector";
import { getCreateMutationFromFormData } from "@/components/form/utils/mutations/getCreateMutationFromFormData";
import { DynamicFieldProps, FormFieldValue } from "@/components/form/type";

export type ProfileData = {
  [key: string]: string | Pick<AttributeType, "value" | "__typename">;
  display_label: string;
  id: string;
};

interface ObjectFormProps extends Omit<DynamicFormProps, "fields" | "onSubmit"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType>;
  currentProfiles?: ProfileData[];
  isFilterForm?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
}

const ObjectForm = ({ kind, isFilterForm, ...props }: ObjectFormProps) => {
  // get all attributes and relationship ordered
  // map them into form fields
  // render form
  const schemas = useAtomValue(schemaState);
  const profiles = useAtomValue(profilesAtom);
  const generics = useAtomValue(genericsState);
  const generic = generics.find((g) => g.kind === kind);
  const [kindToCreate, setKindToCreate] = useState<string>();

  if (!isFilterForm && generic) {
    if (!generic.used_by || generic.used_by.length === 0) {
      return (
        <NoDataFound message="No nodes are referencing this generic. Only nodes can be created." />
      );
    }

    if (!kindToCreate && generic.used_by.length === 1) {
      const genericKind = generic.used_by[0];

      const relatedSchema = schemas.find((schema) => schema.kind === genericKind);

      if (!relatedSchema) return;

      const currentGeneric = {
        value: relatedSchema.kind,
        label: relatedSchema.label ?? relatedSchema.name,
        badge: relatedSchema.namespace,
      };

      setKindToCreate(currentGeneric.value ?? "");
    }

    const items = generic.used_by
      .map((kind) => {
        const relatedSchema = [...schemas, ...profiles].find((schema) => schema.kind === kind);

        if (!relatedSchema) return null;

        return {
          value: relatedSchema.kind,
          label: relatedSchema.label ?? relatedSchema.name,
          badge: relatedSchema.namespace,
        };
      })
      .filter(Boolean) as Array<tComboboxItem>;

    return (
      <>
        <GenericSelector items={items} value={kindToCreate} onChange={setKindToCreate} />
        {kindToCreate && <NodeWithProfileForm kind={kindToCreate} {...props} />}
      </>
    );
  }

  return <NodeWithProfileForm kind={kind} isFilterForm={isFilterForm} {...props} />;
};

type GenericSelectorProps = {
  items: Array<tComboboxItem>;
  value?: string;
  onChange: (item: string) => void;
};

const GenericSelector = (props: GenericSelectorProps) => {
  const id = useId();

  return (
    <div className="p-4 bg-gray-200">
      <Label htmlFor={id}>Select an object type</Label>
      <Combobox id={id} {...props} />
    </div>
  );
};

const NodeWithProfileForm = ({ kind, currentProfiles, ...props }: ObjectFormProps) => {
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
      {"generate_profile" in nodeSchema && nodeSchema.generate_profile && (
        <ProfilesSelector
          schema={nodeSchema}
          defaultValue={currentProfiles}
          value={selectedProfiles}
          onChange={setSelectedProfiles}
          currentProfiles={currentProfiles}
        />
      )}
      <NodeForm schema={nodeSchema} profiles={selectedProfiles} {...props} />
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
  currentObject?: Record<string, AttributeType>;
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
        const mutationString = createToken({
          data: stringifyWithoutQuotes({
            ...data,
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

        toast(() => <Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} created`} />, {
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
