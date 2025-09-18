import ErrorScreen from "@/shared/components/errors/error-screen";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import {
  IpAddressTable,
  type IpAddressTableProps,
} from "@/entities/ipam/ip-addresses/ui/ip-address-table";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import type { ModelSchema } from "@/entities/schema/types";

export interface IpAddressManagerProps {
  schema: ModelSchema;
  baseFilters?: IpAddressTableProps["baseFilters"];
}

export function IpAddressManager({ schema: ipAddressSchema, baseFilters }: IpAddressManagerProps) {
  if (!ipAddressSchema) {
    return <ErrorScreen message={`Schema ${IP_ADDRESS_GENERIC} not found.`} />;
  }

  return (
    <ObjectTableProvider schema={ipAddressSchema}>
      <ObjectsManagerToolbar />
      <IpAddressTable baseFilters={baseFilters} />
    </ObjectTableProvider>
  );
}
