import { toast } from "react-toastify";

import DynamicForm from "@/shared/components/form/dynamic-form";
import type { ProfileData } from "@/shared/components/form/object-form";
import type { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { shouldAllowEmptySubmission } from "@/shared/components/form/utils/shouldAllowEmptySubmission";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";

import { useAuth } from "@/entities/authentication/ui/useAuth";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import type { NodeCore, NodeFieldsWithMetadata, NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/ui/queries/get-number-pools.query";
import type { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import { isTemplateSchema } from "@/entities/schema/utils/is-template-schema";

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles?: Array<ProfileData>;
};

export type NodeFormProps = {
  className?: string;
  schema: NodeSchema | ProfileSchema;
  profiles?: ProfileData[];
  currentObject?: NodeFieldsWithMetadata;
  objectTemplate?: NodeObject | null;
  isFilterForm?: boolean;
  isUpdate?: boolean;
  isBulkUpdate?: boolean;
  onSubmit?: (data: NodeFormSubmitParams) => void;
  onSuccess?: (newObject: NodeCore) => void;
  onCancel?: () => void;
};

export const NodeForm = ({
  className,
  currentObject,
  objectTemplate,
  schema,
  profiles,
  onSuccess,
  isFilterForm,
  onSubmit,
  isUpdate,
  isBulkUpdate,
  ...props
}: NodeFormProps) => {
  const auth = useAuth();
  const { parentData, parentSchema } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();

  const { data: numberPools, isPending } = useGetNumberPools({
    objectKinds: [
      schema.kind!,
      ...(schema.inherit_from ?? []),
      ...(isTemplateSchema(schema) ? [schema.name] : []),
    ],
  });

  if (isPending) return <LoadingIndicator className="my-4" />;

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    objectTemplate,
    auth,
    isFilterForm,
    pools: numberPools,
    isUpdate,
    isBulkUpdate,
    parentSchema,
    parentData,
  });

  async function onSubmitCreate(data: Record<string, FormFieldValue>) {
    const newObject = getCreateMutationFromFormData(fields, data, objectTemplate?.id);
    const isObjectEmpty = Object.keys(newObject).length === 0;
    const isProfilesEmpty = !profiles || profiles.length === 0;

    if (isObjectEmpty && isProfilesEmpty && !shouldAllowEmptySubmission(schema)) {
      return;
    }

    await createObject.mutateAsync(
      {
        objectKind: schema.kind as string,
        data: newObject,
        profileIds: profiles?.map((profile) => profile.id),
      },
      {
        onSuccess: async (newObject) => {
          toast(<Alert type={ALERT_TYPES.SUCCESS} message={`${schema?.name} created`} />, {
            toastId: `alert-success-${schema?.name}-created`,
          });

          if (onSuccess) await onSuccess(newObject);
        },
        onError: (error) => {
          console.error("An error occurred while creating the object: ", error);
        },
      }
    );
  }

  return (
    <DynamicForm
      isBulkUpdate={isBulkUpdate}
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields, profiles }) : onSubmitCreate(formData)
      }
      className={classNames("flex flex-1 flex-col overflow-auto bg-white p-4", className)}
      {...props}
    />
  );
};
