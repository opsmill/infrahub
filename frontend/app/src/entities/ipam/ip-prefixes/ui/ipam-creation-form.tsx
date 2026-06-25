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
    const nodeLabel = getNodeLabel(newNode);
    toast(
      () => (
        <Alert type={ALERT_TYPES.SUCCESS} message={`${props.schema.label} ${nodeLabel} created`} />
      ),
      {
        // Per-node id so two same-kind allocations in quick succession each render their
        // own confirmation. A constant per-kind id makes react-toastify dedupe the second
        // toast while the first is still on screen (autoClose 5s). Matches account-role-form.
        toastId: `alert-success-${props.schema.name}-created-${newNode.id}`,
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
          // A pending from-pool allocation can carry a user-entered prefix length: the
          // new address's mask for an address pool, or the carved-out subnet size for a
          // prefix pool. Both map to the allocation mutation's `prefix_length` argument.
          const pendingFromPool =
            fieldDataForIpField.value &&
            typeof fieldDataForIpField.value === "object" &&
            "from_pool" in fieldDataForIpField.value
              ? fieldDataForIpField.value.from_pool
              : null;

          const allocationData: Record<string, unknown> = {
            id: fieldDataForIpField.source.id,
            data: getCreateMutationFromFormData(formFieldsWithoutIpField, formData),
          };
          // Only send a prefix length when one was entered; otherwise the pool default applies.
          if (typeof pendingFromPool?.prefixlen === "number") {
            allocationData.prefix_length = pendingFromPool.prefixlen;
          }

          await allocateResource.mutateAsync(
            {
              poolGetResourceMutationName: allocateMutationName,
              data: allocationData,
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
