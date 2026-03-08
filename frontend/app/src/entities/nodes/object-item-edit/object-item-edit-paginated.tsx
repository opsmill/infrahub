import { gql } from "@apollo/client";
import { toast } from "react-toastify";

import useQuery from "@/shared/api/graphql/useQuery";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import ObjectForm, { type ObjectFormProps } from "@/shared/components/form/object-form";
import { getUpdateMutationFromFormData } from "@/shared/components/form/utils/mutations/getUpdateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { areObjectArraysEqualById } from "@/shared/utils/array";

import type { DynamicFieldData } from "@/entities/nodes/edit-form-hook/dynamic-control-types";
import { useUpdateObjectMutation } from "@/entities/nodes/object/ui/queries/update-object.mutation";
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

  const updateObject = useUpdateObjectMutation();

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
      const profileIds = profiles?.map((profile) => profile.id);

      await updateObject.mutateAsync(
        {
          objectKind: schema?.kind as string,
          data: {
            id: objectId,
            ...updatedObject,
          },
          ...(areProfilesUpdated ? { profileIds } : {}),
        },
        {
          onSuccess: async () => {
            toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} updated`} />, {
              toastId: "alert-success-updated",
            });

            if (onUpdateComplete) await onUpdateComplete();
          },
          onError: (error) => {
            console.error("Something went wrong while updating the object:", error);
          },
        }
      );
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
