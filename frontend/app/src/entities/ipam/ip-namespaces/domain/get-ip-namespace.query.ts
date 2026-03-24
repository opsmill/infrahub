import { IP_NAMESPACE_GENERIC, IP_NAMESPACE_KIND } from "@/entities/ipam/constants";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import { useObjects } from "@/entities/nodes/object/domain/get-objects.query";
import type { NodeObject } from "@/entities/nodes/types";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

const DEFAULT_NAMESPACE_FILTERS = [{ name: "default__value", value: true }];

/**
 * Fetches a single IP namespace — either by ID or the default one.
 *
 * Two different hooks and schemas are needed because:
 * - By ID: queries BuiltinIPNamespace (the generic) so it works with any concrete
 *   namespace schema, including custom ones that inherit from the generic.
 * - Default: queries IpamNamespace (the concrete) because the `default` attribute
 *   only exists on this type, not on the generic. IpamNamespace is always present
 *   since Infrahub creates it automatically.
 *
 * Only one hook is enabled at a time based on whether an ID is provided.
 */
export function useGetIpNamespace({ ipNamespaceId }: { ipNamespaceId?: string | null } = {}): {
  data: NodeObject | undefined;
  isPending: boolean;
  error: Error | null;
} {
  const { schema: genericSchema } = useSchema(IP_NAMESPACE_GENERIC, { throwIfNotFound: true });
  const { schema: concreteSchema } = useSchema(IP_NAMESPACE_KIND, { throwIfNotFound: true });

  const byIdQuery = useGetObject(
    { objectSchema: genericSchema, objectId: ipNamespaceId ?? "" },
    { enabled: !!ipNamespaceId }
  );

  const defaultQuery = useObjects(
    { schema: concreteSchema, filters: DEFAULT_NAMESPACE_FILTERS },
    { enabled: !ipNamespaceId }
  );

  if (ipNamespaceId) {
    return byIdQuery;
  }

  return {
    ...defaultQuery,
    data: defaultQuery.data?.pages?.[0]?.[0],
  };
}
