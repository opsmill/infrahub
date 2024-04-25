import { gql } from "@apollo/client";
import { useAtom } from "jotai";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import { Select } from "../../components/inputs/select";
import { ALERT_TYPES, Alert } from "../../components/utils/alert";
import graphqlClient from "../../graphql/graphqlClientApollo";
import { updateObjectWithId } from "../../graphql/mutations/objects/updateObjectWithId";
import { getObjectDetailsPaginated } from "../../graphql/queries/objects/getObjectDetails";
import { useAuth } from "../../hooks/useAuth";
import useQuery from "../../hooks/useQuery";
import { currentBranchAtom } from "../../state/atoms/branches.atom";
import { genericsState, schemaState } from "../../state/atoms/schema.atom";
import { schemaKindNameState } from "../../state/atoms/schemaKindName.atom";
import { datetimeAtom } from "../../state/atoms/time.atom";
import getFormStructureForCreateEdit from "../../utils/formStructureForCreateEdit";
import getMutationDetailsFromFormData from "../../utils/getMutationDetailsFromFormData";
import { getSchemaObjectColumns } from "../../utils/getSchemaObjectColumns";
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

  const [schemaList] = useAtom(schemaState);
  const [schemaKindName] = useAtom(schemaKindNameState);
  const [genericsList] = useAtom(genericsState);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [isLoading, setIsLoading] = useState(false);
  const [profile, setProfile] = useState("");

  const schema = schemaList.find((s) => s.kind === objectname);
  const columns = getSchemaObjectColumns(schema);

  const profileName = `Profile${objectname}`;

  const queryString = schema
    ? getObjectDetailsPaginated({
        ...schema,
        columns,
        objectid,
        profile: profileName,
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

  const profiles = data && data[profileName]?.edges?.map((edge) => edge.node);

  const profilesOptions =
    profiles &&
    profiles.map((p) => ({
      id: p.id,
      name: p.display_label,
      values: p,
    }));

  const objectProfiles = objectDetailsData?.profiles?.edges?.map((edge) => edge?.node) ?? [];

  const currentProfile =
    objectProfiles && objectProfiles[0]?.id
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

        toast(
          <Alert type={ALERT_TYPES.SUCCESS} message={`${schemaKindName[schema.kind]} updated`} />,
          { toastId: "alert-success-updated" }
        );

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
      <div className="p-4 pt-3 bg-gray-200">
        <div className="flex items-center">
          <label className="block text-sm font-medium leading-6 text-gray-900">
            Select a Profile <span className="text-xs italic text-gray-500 ml-1">optionnal</span>
          </label>
        </div>
        <Select
          options={profilesOptions}
          value={profile || currentProfile?.id}
          onChange={handleProfileChange}
        />
      </div>

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
