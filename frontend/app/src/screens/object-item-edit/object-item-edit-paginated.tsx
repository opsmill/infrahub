import { ALERT_TYPES, Alert } from "@/components/ui/alert";
import { PROFILE_KIND } from "@/config/constants";
import graphqlClient from "@/graphql/graphqlClientApollo";
import { updateObjectWithId } from "@/graphql/mutations/objects/updateObjectWithId";
import { getObjectDetailsPaginated } from "@/graphql/queries/objects/getObjectDetails";
import useQuery from "@/hooks/useQuery";
import { DynamicFieldData } from "@/screens/edit-form-hook/dynamic-control-types";
import ErrorScreen from "@/screens/errors/error-screen";
import NoDataFound from "@/screens/errors/no-data-found";
import LoadingScreen from "@/screens/loading-screen/loading-screen";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { genericsState, profilesAtom, schemaState } from "@/state/atoms/schema.atom";
import { datetimeAtom } from "@/state/atoms/time.atom";
import getMutationDetailsFromFormData from "@/utils/getMutationDetailsFromFormData";
import { getObjectAttributes, getSchemaObjectColumns } from "@/utils/getSchemaObjectColumns";
import { stringifyWithoutQuotes } from "@/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { useState } from "react";
import { toast } from "react-toastify";
import ObjectForm from "@/components/form/object-form";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: () => void;
  onUpdateComplete?: Function;
  formStructure?: DynamicFieldData[];
}

export default function ObjectItemEditComponent(props: Props) {
  const { objectname, objectid, closeDrawer, onUpdateComplete } = props;

  const schemaList = useAtomValue(schemaState);
  const allProfiles = useAtomValue(profilesAtom);
  const genericsList = useAtomValue(genericsState);
  const profileGeneric = genericsList.find((s) => s.kind === PROFILE_KIND);
  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);
  const [profile] = useState("");

  const nodeSchema = schemaList.find((s) => s.kind === objectname);
  const profileSchema = allProfiles.find((s) => s.kind === objectname);

  const schema = nodeSchema || profileSchema;
  const attributes = getObjectAttributes({ schema: schema, forQuery: true, forProfiles: true });
  const columns = getSchemaObjectColumns({ schema: schema, forQuery: true });

  const displayProfile =
    schema?.generate_profile &&
    !profileGeneric?.used_by?.includes(schema?.kind) &&
    schema.kind !== PROFILE_KIND;
  const profileName = profileSchema ? objectname : `Profile${objectname}`;

  const queryString = schema
    ? getObjectDetailsPaginated({
        kind: schema.kind,
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

  async function onSubmit(data: any) {
    const updatedObject = getMutationDetailsFromFormData(
      schema,
      data,
      "update",
      objectDetailsData,
      currentProfile
    );

    if (Object.keys(updatedObject).length || objectProfiles[0]?.id !== profile) {
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

        toast(() => <Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} updated`} />, {
          toastId: "alert-success-updated",
        });

        closeDrawer();

        if (onUpdateComplete) onUpdateComplete();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }
    }
  }

  return (
    <ObjectForm
      onCancel={closeDrawer}
      onSubmit={onSubmit}
      kind={objectname}
      currentObject={objectDetailsData}
      currentProfile={currentProfile}
      data-cy="object-item-edit"
    />
  );
}
