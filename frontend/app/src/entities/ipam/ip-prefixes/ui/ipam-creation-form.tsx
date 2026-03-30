import { toast } from "react-toastify";

import { NodeForm, type NodeFormProps } from "@/shared/components/form/node-form";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";
import { getCreateMutationFromFormData } from "@/shared/components/form/utils/mutations/getCreateMutationFromFormData";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { ALERT_TYPES, Alert } from "@/shared/components/ui/alert";

import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useGetNextIpAddressAvailable } from "@/entities/ipam/ip-addresses/ui/queries/get-next-ip-address-available.query";
import { useGetNextIpPrefixAvailable } from "@/entities/ipam/ip-prefixes/ui/queries/get-next-ip-prefix-available.query";
import { useCreateObjectMutation } from "@/entities/nodes/object/ui/queries/create-object.mutation";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { NodeAttributeWithMetadata } from "@/entities/nodes/types";
import { useAllocateResourceMutation } from "@/entities/resource-manager/ui/queries/allocate-resource.mutation";
import { getAllocateMutationNameFromSchema } from "@/entities/resource-manager/utils/get-allocate-mutation-name-from-schema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export interface IpamCreationFormProps extends NodeFormProps {}

function IpamCreationForm(props: IpamCreationFormProps) {
  const allocateResource = useAllocateResourceMutation();
  const createObject = useCreateObjectMutation();
  const { parentData } = useCurrentFormContext();

  const isIpPrefixSchema = isOfKind(IP_PREFIX_GENERIC, props.schema);
  const isIpAddressSchema = isOfKind(IP_ADDRESS_GENERIC, props.schema);

  const ipFieldName = isIpPrefixSchema ? "prefix" : "address";

  const { data: nextIpAddress, isLoading: isIpAddressLoading } = useGetNextIpAddressAvailable(
    { parentPrefixId: parentData?.id },
    // Enable fetching the next available IP address only if:
    // - The current schema is for an IP address
    // - The current object does NOT already have an address set
    { enabled: isIpAddressSchema && !props.currentObject?.address }
  );
  const { data: nextIpPrefix, isLoading: isIpPrefixLoading } = useGetNextIpPrefixAvailable(
    { parentPrefixId: parentData?.id },
    {
      // Enable fetching the next available IP prefix only if:
      // - The current schema is for an IP prefix
      // - The current object does NOT already have a prefix set
      enabled: isIpPrefixSchema && !props.currentObject?.prefix,
    }
  );

  if (parentData && (isIpAddressLoading || isIpPrefixLoading)) {
    return <LoadingIndicator className="mt-4" />;
  }

  const nextIpValue = isIpPrefixSchema ? nextIpPrefix : nextIpAddress;

  const onSuccess: NodeFormProps["onSuccess"] = (newNode) => {
    toast(
      () => (
        <Alert
          type={ALERT_TYPES.SUCCESS}
          message={`${props.schema.label} ${getNodeLabel(newNode)} created`}
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
      currentObject={
        nextIpValue
          ? {
              ...props.currentObject,
              [ipFieldName]: {
                value: nextIpValue,
                is_default: false,
                is_from_profile: false,
                is_protected: false,
                is_visible: true,
                owner: null,
                source: null,
                updated_at: new Date().toISOString(),
              } satisfies NodeAttributeWithMetadata,
            }
          : props.currentObject
      }
      onSubmit={async ({ fields, formData }) => {
        // Remove the IP field if it's being allocated from a pool
        const formFieldsWithoutIpField = fields.filter(({ name }) => name !== ipFieldName);
        const fieldDataForIpField = formData[ipFieldName];
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
