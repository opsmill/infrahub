import ErrorScreen from "@/shared/components/errors/error-screen";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { IpAddressManager } from "@/entities/ipam/ip-addresses/ui/ip-address-manager";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IpNamespaceTabs } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-tabs";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const Component = () => {
  const { currentIpNamespace } = useCurrentIpNamespace();
  const { schema: ipNamespaceSchema } = useSchema(currentIpNamespace.__typename);
  const { schema: ipAddressSchema } = useSchema(IP_ADDRESS_GENERIC);

  if (!ipNamespaceSchema) {
    return <ErrorScreen message={`Schema ${currentIpNamespace.__typename} not found.`} />;
  }

  if (!ipAddressSchema) {
    return <ErrorScreen message={`Schema ${IP_ADDRESS_GENERIC} not found.`} />;
  }

  return (
    <>
      <IpNamespaceTabs schema={ipNamespaceSchema} objectId={currentIpNamespace.id} />

      <IpAddressManager
        schema={ipAddressSchema}
        baseFilters={[{ name: "ip_namespace__ids", value: [{ id: currentIpNamespace.id }] }]}
      />
    </>
  );
};
