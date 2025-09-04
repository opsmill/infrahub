import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";

import { IP_ADDRESS_GENERIC, IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { IpAddressManager } from "@/entities/ipam/ip-addresses/ui/ip-address-manager";
import { IpPrefixManager } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-manager";
import { RelationshipTable } from "@/entities/nodes/relationships/ui/relationship-table/relationship-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const Component = () => {
  const { objectKind, objectId, relationshipName } = useParams() as {
    objectKind: string;
    objectId: string;
    relationshipName: string;
  };
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema for ${objectKind} not found.`} />;
  }

  const relationship = schema.relationships?.find((r) => r.name === relationshipName);
  if (!relationship) {
    return <ErrorScreen message={`Relationship ${relationshipName} not found.`} />;
  }
  const { schema: peerSchema } = useSchema(relationship.peer);
  if (!peerSchema) {
    return <ErrorScreen message={`Schema for ${relationship.peer} not found.`} />;
  }

  if (isOfKind(IP_ADDRESS_GENERIC, peerSchema)) {
    return (
      <IpAddressManager
        schema={peerSchema}
        baseFilters={[{ name: "ip_prefix__ids", value: [{ id: objectId }] }]}
      />
    );
  }

  if (isOfKind(IP_PREFIX_GENERIC, peerSchema)) {
    return (
      <IpPrefixManager
        schema={peerSchema}
        baseFilters={[{ name: "parent__ids", value: [{ id: objectId }] }]}
      />
    );
  }

  return (
    <RelationshipTable
      parentId={objectId}
      parentKind={objectKind}
      relationshipName={relationshipName}
      relationshipSchema={peerSchema}
    />
  );
};
