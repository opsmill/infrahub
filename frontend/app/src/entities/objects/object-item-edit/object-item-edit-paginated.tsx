import { currentBranchAtom } from "@/entities/branches/branches.atom";
import { updateObjectWithId } from "@/entities/objects/api/updateObjectWithId";
import { DynamicFieldData } from "@/entities/objects/edit-form-hook/dynamic-control-types";
import { generateObjectEditFormQuery } from "@/entities/objects/object-item-edit/generateObjectEditFormQuery";
import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import ObjectForm, { ObjectFormProps } from "@/shared/components/form/object-form";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import LoadingScreen from "@/shared/components/loading-screen";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import useQuery from "@/shared/hooks/useQuery";
import { useSchema } from "@/shared/hooks/useSchema";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { areObjectArraysEqualById } from "@/shared/utils/array";
import { stringifyWithoutQuotes } from "@/shared/utils/string";
import { gql } from "@apollo/client";
import { useAtomValue } from "jotai/index";
import { toast } from "react-toastify";

interface Props {
  objectname: string;
  objectid: string;
  closeDrawer: () => void;
  onUpdateComplete?: () => void;
  formStructure?: DynamicFieldData[];
}

export default function ObjectItemEditComponent(props: Props) {
  const { objectname, objectid, closeDrawer, onUpdateComplete } = props;

  const { schema } = useSchema(objectname);

  if (!schema) {
    return <NoDataFound message={`Schema ${objectname} not found`} />;
  }

  const query = gql(
    generateObjectEditFormQuery({
      schema,
      objectId: objectid,
    })
  );

  const { loading, error, data } = useQuery(query, { skip: !schema });

  const branch = useAtomValue(currentBranchAtom);
  const date = useAtomValue(datetimeAtom);

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

  const objectProfiles = objectDetailsData?.profiles?.edges?.map((edge) => edge?.node) ?? [];

  const onSubmit: ObjectFormProps["onSubmit"] = async ({ fields, formData, profiles }) => {
    const updatedObject = getUpdateMutationFromFormData({ formData, fields });
    const isObjectUpdated = Object.keys(updatedObject).length > 0;

    const areProfilesUpdated = !!profiles && !areObjectArraysEqualById(profiles, objectProfiles);

    if (isObjectUpdated || areProfilesUpdated) {
      const profilesId = profiles?.map((profile) => ({ id: profile.id })) ?? [];

      try {
        const mutationString = updateObjectWithId({
          kind: schema?.kind,
          data: stringifyWithoutQuotes({
            id: objectid,
            ...updatedObject,
            ...(areProfilesUpdated ? { profiles: profilesId } : {}),
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

        if (onUpdateComplete) onUpdateComplete();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }
    }
  };

  return (
    <ObjectForm
      onCancel={closeDrawer}
      onSubmit={onSubmit}
      onUpdateComplete={onUpdateComplete}
      kind={objectname}
      currentObject={objectDetailsData}
      currentProfiles={objectProfiles}
      data-cy="object-item-edit"
      isUpdate
    />
  );
}
