import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import { Select } from "../../components/inputs/select";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { PROFILE_KIND } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { createObject } from "../../graphql/mutations/objects/createObject";
import { getObjectItemsPaginated } from "../../graphql/queries/objects/getObjectItems";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, profilesAtom, schemaState } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { getObjectAttributes } from "../../utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import { Form } from "../edit-form-hook/form";

interface iProps {
  objectname?: string;
  onCancel?: Function;
  onCreate: Function;
  refetch?: Function;
  formStructure?: DynamicFieldData[];
  customObject?: any;
  preventObjectsCreation?: boolean;
  submitLabel?: string;
}

export default function ObjectItemCreate(props: iProps) {
  const {
    objectname,
    onCreate,
    onCancel,
    refetch,
    formStructure,
    customObject = {},
    preventObjectsCreation,
    submitLabel,
  } = props;

  const schemaList = useAtomValue(schemaState);
  const genericsList = useAtomValue(genericsState);
  const profileGeneric = genericsList.find((s) => s.kind === PROFILE_KIND);
  const profilesList = useAtomValue(profilesAtom);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [kind, setKind] = useState("");
  const [profile, setProfile] = useState("");

  const generic = genericsList.find((s) => s.kind === objectname);

  const isGeneric = !!generic;
  const isProfileCreationForm = objectname === PROFILE_KIND;

  const schema = isProfileCreationForm
    ? profilesList.find((profile) => profile.kind === kind)
    : schemaList.find((s) => (isGeneric ? s.kind === kind : s.kind === objectname));

  const isEditingProfile = kind && profileGeneric?.used_by?.includes(kind);

  // Adds "Profile" before kind to get profiles, eccept for profiles themselves
  const profileName = `Profile${isGeneric && kind ? kind : objectname}`;

  const displayProfile =
    schema && !profileGeneric?.used_by?.includes(schema.kind) && schema.kind !== PROFILE_KIND;

  // Get object's attributes to get them from the profile data
  const attributes = getObjectAttributes({ schema, forQuery: true, forProfiles: true });

  const queryString = getObjectItemsPaginated({
    kind: profileName,
    attributes,
  });

  const query = gql`
    ${queryString}
  `;

  const { data } = useQuery(query, {
    skip: !(!!generic || !!schema) || (isGeneric && !kind) || isEditingProfile,
  });

  const profiles = data && data[profileName]?.edges?.map((edge) => edge.node);

  const profilesOptions =
    profiles &&
    profiles.map((profile) => ({
      id: profile.id,
      name: profile.display_label,
      values: profile,
    }));

  const kindOptions = generic?.used_by?.map((kind: string) => ({ id: kind, name: kind })) ?? [];

  const currentProfile = profilesOptions?.find((p) => p.id === profile)?.values;

  const fields =
    formStructure ??
    getFormStructureForCreateEdit({
      schema,
      schemas: schemaList,
      generics: genericsList,
      profile: currentProfile,
    });

  const handleProfileChange = (newProfile: string) => {
    setProfile(newProfile);
  };

  const handleKindChange = (newKind: string) => {
    setKind(newKind);
  };

  async function onSubmit(data: any) {
    setIsLoading(true);

    try {
      const newObject = getMutationDetailsFromFormData(
        schema,
        data,
        "create",
        null,
        currentProfile
      );

      if (!Object.keys(newObject).length) {
        return;
      }

      const mutationString = createObject({
        kind: schema?.kind,
        data: stringifyWithoutQuotes({
          ...newObject,
          ...customObject,
          ...(profile ? { profiles: [{ id: profile }] } : {}),
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

      if (onCreate) {
        onCreate(result?.data?.[`${schema?.kind}Create`]);
      }

      if (refetch) refetch();

      setIsLoading(false);
    } catch (error: any) {
      console.error("An error occurred while creating the object: ", error);

      setIsLoading(false);
    }
  }

  return (
    <div className="bg-custom-white flex flex-col flex-1 overflow-auto">
      {isGeneric && (
        <div className="p-4 pt-3 bg-gray-200">
          <div className="flex items-center">
            <label className="block text-sm font-medium leading-6 text-gray-900">
              Select an object type
            </label>
          </div>
          <Select options={kindOptions} value={kind} onChange={handleKindChange} preventEmpty />
        </div>
      )}

      {(!isGeneric || (isGeneric && kind)) && displayProfile && (
        <div className="p-4 pt-3 bg-gray-100">
          <div className="flex items-center">
            <label className="block text-sm font-medium leading-6 text-gray-900">
              Select a Profile <span className="text-xs italic text-gray-500 ml-1">optional</span>
            </label>
          </div>
          <Select options={profilesOptions} value={profile} onChange={handleProfileChange} />
        </div>
      )}

      {schema && fields && (
        <Form
          onSubmit={onSubmit}
          onCancel={onCancel}
          fields={fields}
          isLoading={isLoading}
          submitLabel={submitLabel ?? "Create"}
          preventObjectsCreation={preventObjectsCreation}
        />
      )}
    </div>
  );
}
