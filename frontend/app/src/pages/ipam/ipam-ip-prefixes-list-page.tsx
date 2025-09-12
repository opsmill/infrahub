import ErrorScreen from "@/shared/components/errors/error-screen";

import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { useCurrentIpNamespace } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-provider";
import { IpNamespaceTabs } from "@/entities/ipam/ip-namespaces/ui/ip-namespace-tabs";
import { IpPrefixManager } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-manager";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const Component = () => {
  const { currentIpNamespace } = useCurrentIpNamespace();
  const { schema } = useSchema(currentIpNamespace.__typename);
  const { schema: ipPrefixSchema } = useSchema(IP_PREFIX_GENERIC);

  if (!schema) {
    return <ErrorScreen message={`Schema ${currentIpNamespace.__typename} not found.`} />;
  }

  if (!ipPrefixSchema) {
    return <ErrorScreen message={`Schema ${IP_PREFIX_GENERIC} not found.`} />;
  }

  return (
    <>
      <IpNamespaceTabs schema={schema} objectId={currentIpNamespace.id} />

      <IpPrefixManager
        schema={ipPrefixSchema}
        baseFilters={[{ name: "ip_namespace__ids", value: [{ id: currentIpNamespace.id }] }]}
      />
    </>
  );
};
