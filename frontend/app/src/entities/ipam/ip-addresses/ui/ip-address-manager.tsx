import ErrorScreen from "@/shared/components/errors/error-screen";

import { IP_ADDRESS_GENERIC } from "@/entities/ipam/ip-addresses/domain/model/ip-address";
import {
  IpAddressTable,
  type IpAddressTableProps,
} from "@/entities/ipam/ip-addresses/ui/ip-address-table";
import { IP_ADDRESS_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpAddressManagerProps {
  schema: ModelSchema;
  baseFilters?: IpAddressTableProps["baseFilters"];
}

export function IpAddressManager({ schema: ipAddressSchema, baseFilters }: IpAddressManagerProps) {
  if (!ipAddressSchema) {
    return <ErrorScreen message={`Schema ${IP_ADDRESS_GENERIC} not found.`} />;
  }

  return (
    <ObjectTableProvider
      schema={ipAddressSchema}
      columnSurface={IP_ADDRESS_COLUMN_SURFACE}
      supportsColumnVisibility
    >
      <ObjectsManagerToolbar />
      <IpAddressTable baseFilters={baseFilters} />
    </ObjectTableProvider>
  );
}
