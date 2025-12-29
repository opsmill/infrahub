import { gql } from "@apollo/client";
import { useAtomValue } from "jotai";
import { toast } from "react-toastify";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { datetimeAtom } from "@/shared/stores/time.atom";
import { areObjectArraysEqualById } from "@/shared/utils/array";
import { stringifyWithoutQuotes } from "@/shared/utils/string";

import { useCurrentBranch } from "@/entities/branches/ui/branches-provider";
import { updateObjectWithId } from "@/entities/nodes/api/updateObjectWithId";
import type { DynamicFieldData } from "@/entities/nodes/edit-form-hook/dynamic-control-types";
import { generateObjectEditFormQuery } from "@/entities/nodes/object-item-edit/generateObjectEditFormQuery";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

interface Props {
  objectname: string;
  objectId: string;
  closeDrawer: () => void;
  onUpdateComplete?: () => void;
  formStructure?: DynamicFieldData[];
}

export default function ObjectItemEditComponent(props: Props) {
  const { objectname, objectId, closeDrawer, onUpdateComplete } = props;

  const { schema } = useSchema(objectname);

  if (!schema) {
    return <NoDataFound message={`Schema ${objectname} not found`} />;
  }

  const query = gql(
    generateObjectEditFormQuery({
      schema,
      objectId,
    })
  );

  const { loading, error, data } = useQuery(query, { skip: !schema });

  const { currentBranch } = useCurrentBranch();
  const date = useAtomValue(datetimeAtom);

  if (error) {
    return <ErrorScreen message="Something went wrong when fetching the object details." />;
  }

  if (loading || !schema) {
    return <LoadingIndicator className="p-4" />;
  }

  if (!data) {
    return <NoDataFound message="No details found." />;
  }

  const objectDetailsData = data[schema.kind as string]?.edges[0]?.node;

  const objectProfiles = objectDetailsData?.profiles?.edges?.map((edge: any) => edge?.node) ?? [];

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
            id: objectId,
            ...updatedObject,
            ...(areProfilesUpdated ? { profiles: profilesId } : {}),
          }),
        });

        const mutation = gql`
          ${mutationString}
        `;

        await graphqlClient.mutate({
          mutation,
          context: { branch: currentBranch.name, date },
        });

        toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} updated`} />, {
          toastId: "alert-success-updated",
        });

        if (onUpdateComplete) await onUpdateComplete();
      } catch (e) {
        console.error("Something went wrong while updating the object:", e);
      }
    }
  };

  return (
    <ObjectForm
      onCancel={closeDrawer}
      onSubmit={onSubmit}
      onSuccess={onUpdateComplete}
      kind={objectname}
      currentObject={objectDetailsData}
      currentProfiles={objectProfiles}
      data-cy="object-item-edit"
      isUpdate
    />
  );
}
