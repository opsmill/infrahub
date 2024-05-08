import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import { Select } from "../../components/inputs/select";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import { PROFILE_KIND } from "../../config/constants";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import { useAuth } from "../../hooks/useAuth";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, profilesAtom, schemaState } from "../../state/atoms/schema.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { getObjectAttributes, getSchemaObjectColumns } from "../../utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "../../utils/string";
import { DynamicFieldData } from "../edit-form-hook/dynamic-control-types";
import EditFormHookComponent from "../edit-form-hook/edit-form-hook-component";
import ErrorScreen from "../error-screen/error-screen";
import LoadingScreen from "../loading-screen/loading-screen";
import NoDataFound from "../no-data-found/no-data-found";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: Function;
  onUpdateComplete: Function;
  formStructure?: DynamicFieldData[];
}

export default function ObjectItemEditComponent(props: Props) {
  const {
    objectname,
    objectid,
    closeDrawer,
    onUpdateComplete,
    formStructure: formStructureFromProps,
  } = props;

  const user = useAuth();

  const schemaList = useAtomValue(schemaState);
  const allProfiles = useAtomValue(profilesAtom);
  const genericsList = useAtomValue(genericsState);
  const profileGeneric = genericsList.find((s) => s.kind === PROFILE_KIND);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [profile, setProfile] = useState("");

  const nodeSchema = schemaList.find((s) => s.kind === objectname);
  const profileSchema = allProfiles.find((s) => s.kind === objectname);

  const schema = nodeSchema || profileSchema;
  const attributes = getObjectAttributes({ schema: schema, forQuery: true, forProfiles: true });
  const columns = getSchemaObjectColumns({ schema: schema, forQuery: true });

  const displayProfile =
    schema && !profileGeneric?.used_by?.includes(schema?.kind) && schema.kind !== PROFILE_KIND;
  const profileName = profileSchema ? objectname : `Profile${objectname}`;

  const queryString = schema
    ? getObjectDetailsPaginated({
        ...schema,
        columns,
        attributes, // used for profile
        objectid,
        profile: displayProfile && profileName,
        queryProfiles: displayProfile,
      })
    : // Empty query to make the gql parsing work
      // TODO: Find another solution for queries while loading schema
      "query { ok }";

  const query = gql`
    ${queryString}
  `;

  const { loading, error, data } = useQuery(query, { skip: !schema });

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  if (loading || !schema) {
    return <LoadingScreen />;
  }

  if (!data) {
    return <NoDataFound message="No details found." />;
  }

  const objectDetailsData = data[schema.kind]?.edges[0]?.node;

  const profiles = data[profileName]?.edges?.map((edge) => edge.node);

  const profilesOptions =
    profiles &&
    profiles.map((p) => ({
      id: p.id,
      name: p.display_label,
      values: p,
    }));

  const objectProfiles = objectDetailsData?.profiles?.edges?.map((edge) => edge?.node) ?? [];

  // Get profile from object or from the locally selected one
  const currentProfile =
    objectProfiles &&
    objectProfiles[0]?.id &&
    // If the profile is not selected, or it is selected but the same as the one from the object
    (!profile || (profile && objectProfiles[0]?.id === profile))
      ? profilesOptions?.find((p) => p.id === objectProfiles[0].id)?.values
      : profilesOptions?.find((p) => p.id === profile)?.values;

  const formStructure =
    formStructureFromProps ??
    getFormStructureForCreateEdit({
      schema,
      schemas: schemaList,
      generics: genericsList,
      row: objectDetailsData,
      user,
      isUpdate: true,
      profile: currentProfile,
    });

  const handleProfileChange = (newProfile: string) => {
    setProfile(newProfile);
  };

  async function onSubmit(data: any) {
    const updatedObject = getMutationDetailsFromFormData(
      schema,
      data,
      "update",
      objectDetailsData,
      currentProfile
    );

    if (Object.keys(updatedObject).length || objectProfiles[0]?.id !== profile) {
      setIsLoading(true);

      try {
        const mutationString = updateObjectWithId({
          kind: schema?.kind,
          data: stringifyWithoutQuotes({
            id: objectid,
            ...updatedObject,
            ...(profile ? { profiles: [{ id: profile }] } : {}),
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: branch?.name, date },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} updated`} />, {
          toastId: "alert-success-updated",
        });

        closeDrawer();

        onUpdateComplete();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }

      setIsLoading(false);
    }
  }

  return (
    <div className="bg-custom-white flex-1 overflow-auto flex flex-col" data-cy="object-item-edit">
      {displayProfile && (
        <div className="p-4 pt-3 bg-gray-100">
          <div className="flex items-center">
            <label className="block text-sm font-medium leading-6 text-gray-900">
              Select a Profile <span className="text-xs italic text-gray-500 ml-1">optional</span>
            </label>
          </div>
          <Select
            options={profilesOptions}
            value={profile || currentProfile?.id}
            onChange={handleProfileChange}
          />
        </div>
      )}

      {formStructure && (
        <EditFormHookComponent
          onCancel={closeDrawer}
          onSubmit={onSubmit}
          fields={formStructure}
          isLoading={isLoading}
        />
      )}
    </div>
  );
}
