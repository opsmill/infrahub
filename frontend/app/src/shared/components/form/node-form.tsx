import { useAuth } from "@/entities/authentication/ui/useAuth";
import { AttributeType, RelationshipType } from "@/entities/nodes/getObjectItemDisplayValue";
import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { NodeCore, NodeObject } from "@/entities/nodes/types";
import { useGetNumberPools } from "@/entities/resource-manager/domain/get-number-pools.query";
import { NodeSchema, ProfileSchema } from "@/entities/schema/types";
import DynamicForm from "@/shared/components/form/dynamic-form";
import { ProfileData } from "@/shared/components/form/object-form";
import { DynamicFieldProps, FormFieldValue } from "@/shared/components/form/type";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getFormFieldsFromSchema } from "@/shared/components/form/utils/getFormFieldsFromSchema";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { classNames } from "@/shared/utils/common";
import { toast } from "react-toastify";

export type NodeFormSubmitParams = {
  fields: Array<DynamicFieldProps>;
  formData: Record<string, FormFieldValue>;
  profiles?: Array<ProfileData>;
};

export type NodeFormProps = {
  className?: string;
  schema: NodeSchema | ProfileSchema;
  profiles?: ProfileData[];
  currentObject?: Record<string, AttributeType | RelationshipType>;
  objectTemplate?: NodeObject | null;
  isFilterForm?: boolean;
  isUpdate?: boolean;
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
  ...props
}: NodeFormProps) => {
  const auth = useAuth();
  const { parentData, parentSchema } = useCurrentFormContext();
  const createObject = useCreateObjectMutation();

  const { data: numberPools, isPending } = useGetNumberPools({
    objectKinds: [schema.kind as string, ...(schema.inherit_from ?? [])],
  });

  if (isPending) return <LoadingIndicator className="mt-4" />;

  const fields = getFormFieldsFromSchema({
    schema,
    profiles,
    initialObject: currentObject,
    objectTemplate,
    auth,
    isFilterForm,
    pools: numberPools,
    isUpdate,
    parentSchema,
    parentData,
  });

  async function onSubmitCreate(data: Record<string, FormFieldValue>) {
    const newObject = getCreateMutationFromFormData(fields, data);
    const isObjectEmpty = Object.keys(newObject).length === 0;
    const isProfilesEmpty = !profiles || profiles.length === 0;

    if (isObjectEmpty && isProfilesEmpty) {
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
      fields={fields}
      onSubmit={(formData: Record<string, FormFieldValue>) =>
        onSubmit ? onSubmit({ formData, fields, profiles }) : onSubmitCreate(formData)
      }
      className={classNames("bg-white flex flex-col flex-1 overflow-auto p-4", className)}
      {...props}
    />
  );
};
