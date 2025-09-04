import { useParams } from "react-router";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { Card } from "@/shared/components/ui/card";

import { NodeEvents } from "@/entities/events/ui/node-details-events";
import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import { IpAddressDetails } from "@/entities/ipam/ip-addresses/ui/ip-address-details";
import { IpPrefixDetails } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-details";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";
import { isOfKind } from "@/entities/schema/utils/is-of-kind";

export const Component = () => {
  const { objectKind, objectId } = useParams() as { objectKind: string; objectId: string };
  const { schema } = useSchema(objectKind);

  if (!schema) {
    return <ErrorScreen message={`Schema for ${objectKind} not found.`} />;
  }

  return (
    <div className="flex flex-wrap items-start gap-2 p-2 overflow-auto">
      <Card className="p-0">
        <h3 className="font-semibold border-b p-2 border-gray-200">Details</h3>
        {isOfKind(IP_ADDRESS_GENERIC, schema) ? (
          <IpAddressDetails ipAddressSchema={schema} ipAddressId={objectId} />
        ) : (
          <IpPrefixDetails prefixSchema={schema} prefixId={objectId} />
        )}
      </Card>

      <Card className="p-0 grow">
        <h3 className="font-semibold p-2 border-b  border-gray-200">Activities</h3>
        <NodeEvents objectKind={objectKind} objectId={objectId} />
      </Card>
    </div>
  );
};
