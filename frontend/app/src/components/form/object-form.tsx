import {
  genericsState,
  iNodeSchema,
  IProfileSchema,
  profilesAtom,
  schemaState,
} from "@/state/atoms/schema.atom";
import { useAtomValue } from "jotai/index";
import { getFormFieldsFromSchema } from "./utils";
import { useId, useState } from "react";
import { Combobox, MultiCombobox, tComboboxItem } from "@/components/ui/combobox";
import NoDataFound from "@/screens/errors/no-data-found";
import Label from "@/components/ui/label";
import { gql } from "@apollo/client";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import ErrorScreen from "@/screens/errors/error-screen";
import getMutationDetailsFromFormData from "@/utils/getMutationDetailsFromFormData";
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
import useQuery from "@/hooks/useQuery";
import { getProfiles } from "@/graphql/queries/objects/getProfiles";
import { getObjectAttributes } from "@/utils/getSchemaObjectColumns";

interface ObjectFormProps extends Omit<DynamicFormProps, "fields"> {
  kind: string;
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType>;
  currentProfile?: Record<string, Pick<AttributeType, "value" | "__typename">>;
  isFilterForm?: boolean;
  onSubmit?: (data: any) => Promise<void>;
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

const NodeWithProfileForm = ({ kind, currentProfile, ...props }: ObjectFormProps) => {
  const nodes = useAtomValue(schemaState);
  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);
  const [selectedProfiles, setSelectedProfiles] = useState<
    Record<string, Pick<AttributeType, "value" | "__typename">> | undefined
  >(currentProfile);
  console.log("selectedProfiles: ", selectedProfiles);
  const nodeSchema = [...nodes, ...generics, ...profiles].find((node) => node.kind === kind);

  if (!nodeSchema) {
    return <NoDataFound message={`${kind} schema not found. Try to reload the page.`} />;
  }

  return (
    <>
      {nodeSchema.generate_profile && (
        <ProfilesSelector
          schema={nodeSchema}
          value={selectedProfiles}
          onChange={setSelectedProfiles}
        />
      )}
      <NodeForm schema={nodeSchema} profiles={selectedProfiles} {...props} />
    </>
  );
};

type ProfilesSelectorProps = {
  schema: iNodeSchema;
  value?: Record<string, Pick<AttributeType, "value" | "__typename">>;
  onChange: (item: Record<string, Pick<AttributeType, "value" | "__typename">>) => void;
};

const ProfilesSelector = ({ schema, value, onChange }: ProfilesSelectorProps) => {
  const id = useId();

  const generics = useAtomValue(genericsState);
  const profiles = useAtomValue(profilesAtom);

  const nodeGenerics = schema?.inherit_from ?? [];

  // Get all available generic profiles
  const nodeGenericsProfiles = nodeGenerics
    // Find all generic schema
    .map((nodeGeneric) => generics.find((generic) => generic.kind === nodeGeneric))
    // Filter for generate_profile ones
    .filter((generic) => generic.generate_profile)
    // Get only the kind
    .map((generic) => generic.kind)
    .filter(Boolean);

  // The profiles should include the current object profile + all generic profiles
  const kindList = [schema.kind, ...nodeGenericsProfiles];

  // Add attributes for each profiles to get the values in the form
  const profilesList = kindList
    .map((profile) => {
      // Get the profile schema for the current kind
      const profileSchema = profiles.find((profileSchema) => profileSchema.name === profile);

      // Get attributes for query + form data
      const attributes = getObjectAttributes({ schema: profileSchema, forListView: true });

      if (!attributes.length) return null;

      return {
        name: profileSchema.kind,
        attributes,
      };
    })
    .filter(Boolean);

  // Get all profiles kind to retrieve the informations from the result
  const profilesKindList = profilesList.map((profile) => profile.kind);

  if (!profilesList.length)
    return <ErrorScreen message="Something went wrong while fetching profiles" />;

  const queryString = getProfiles({ profiles: profilesList });

  const query = gql`
    ${queryString}
  `;

  const { data, error, loading } = useQuery(query);

  if (loading) return <LoadingScreen size={30} hideText className="p-4 pb-0" />;

  if (error) return <ErrorScreen message={error.message} />;

  // Get data for each profile in the query result
  const profilesData = profilesKindList.reduce(
    (acc, profile) => [...acc, ...(data?.[profile!]?.edges ?? [])],
    []
  );

  if (!profilesData || profilesData.length === 0) return null;

  return (
    <div className="p-4 bg-gray-100">
      <Label htmlFor={id}>
        Select profiles <span className="text-xs italic text-gray-500 ml-1">optional</span>
      </Label>

      <MultiCombobox
        id={id}
        items={profilesData.map((edge: any) => ({
          value: edge.node,
          label: edge.node.display_label,
        }))}
        onChange={onChange}
        value={value}
      />
    </div>
  );
};

type NodeFormProps = {
  className?: string;
  schema: iNodeSchema | IProfileSchema;
  profiles?: IProfileSchema[];
  onSuccess?: (newObject: any) => void;
  currentObject?: Record<string, AttributeType>;
  isFilterForm?: boolean;
  onSubmit?: (data: any) => void;
};

const NodeForm = ({
  className,
  currentObject,
  schema,
  profiles,
  onSuccess,
  isFilterForm,
  onSubmit: onSubmitOverride,
  ...props
}: NodeFormProps) => {
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const schemas = useAtomValue(schemaState);
  const [filters] = useFilters();
  const { data, permissions } = useAuth();

  const fields = getFormFieldsFromSchema({
    schema,
    schemas,
    profiles,
    initialObject: currentObject,
    user: { ...data, permissions },
    isFilterForm,
    filters,
  });

  async function onSubmit(data: any) {
    try {
      const newObject = getMutationDetailsFromFormData(schema, data, "create", null, profiles);

      if (!Object.keys(newObject).length) {
        return;
      }

      const profilesId = profiles?.map((profile) => ({ id: profile.id })) ?? [];

      const mutationString = createObject({
        kind: schema?.kind,
        data: stringifyWithoutQuotes({
          ...newObject,
          ...(profilesId.length ? { profiles: profilesId } : {}),
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
    } catch (error: any) {
      console.error("An error occurred while creating the object: ", error);
    }
  }

  return (
    <DynamicForm
      fields={fields}
      onSubmit={onSubmitOverride || onSubmit}
      className={classNames("bg-custom-white flex flex-col flex-1 overflow-auto p-4", className)}
      {...props}
    />
  );
};

export default ObjectForm;
