import { useCreateObjectMutation } from "@/entities/nodes/object/domain/create-object.mutation";
import { useAllocateResourceMutation } from "@/entities/resource-manager/domain/allocate-resource.mutation";
import { getAllocateMutationNameFromSchema } from "@/entities/resource-manager/utils/get-allocate-mutation-name-from-schema";
import { NodeForm, NodeFormProps } from "@/shared/components/form/node-form";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";
import { toast } from "react-toastify";

export interface IpamCreationFormProps extends NodeFormProps {}

function IpamCreationForm(props: IpamCreationFormProps) {
  const allocateResource = useAllocateResourceMutation();
  const createObject = useCreateObjectMutation();

  const onSuccess: NodeFormProps["onSuccess"] = (newNode) => {
    toast(
      () => (
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`${props.schema.label} ${newNode.display_label} created`}
        />
      ),
      {
        toastId: `alert-success-${props.schema.name}-created`,
      }
    );

    props.onSuccess?.(newNode);
  };

  const onError = (error: Error) => {
    console.error("An error occurred while creating the object:", error);
  };

  return (
    <NodeForm
      {...props}
      onSubmit={async ({ fields, formData }) => {
        // prefix and address are fields that pool allocates
        const formFieldsWithoutIpField = fields.filter(
          ({ name }) => name !== "prefix" && name !== "address"
        );

        const fieldDataForIpField = formData.prefix ?? formData.address;

        const allocateMutationName = getAllocateMutationNameFromSchema(props.schema);
        if (fieldDataForIpField?.source?.type === "pool" && allocateMutationName) {
          await allocateResource.mutateAsync(
            {
              poolGetResourceMutationName: allocateMutationName,
              poolId: fieldDataForIpField.source.id,
              data: getCreateMutationFromFormData(formFieldsWithoutIpField, formData),
            },
            {
              onSuccess,
              onError,
            }
          );
        } else {
          await createObject.mutateAsync(
            {
              objectKind: props.schema.kind as string,
              data: getCreateMutationFromFormData(fields, formData),
            },
            {
              onSuccess,
              onError,
            }
          );
        }
      }}
    />
  );
}

export default IpamCreationForm;
