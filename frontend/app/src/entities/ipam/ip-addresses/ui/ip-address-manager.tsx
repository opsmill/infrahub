import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import {
  IpAddressTable,
  IpAddressTableProps,
} from "@/entities/ipam/ip-addresses/ui/ip-address-table";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { ModelSchema } from "@/entities/schema/types";
import ErrorScreen from "@/shared/components/errors/error-screen";

export interface IpAddressManagerProps {
  schema: ModelSchema;
  baseFilters?: IpAddressTableProps["baseFilters"];
}

export function IpAddressManager({ schema: ipAddressSchema, baseFilters }: IpAddressManagerProps) {
  if (!ipAddressSchema) {
    return <ErrorScreen message={`Schema ${IP_ADDRESS_GENERIC} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={IP_ADDRESS_GENERIC}>
      {({ permission }) => {
        return (
          <>
            <ObjectsManagerToolbar permission={permission} schema={ipAddressSchema} />
            <IpAddressTable
              permission={permission}
              schema={ipAddressSchema}
              baseFilters={baseFilters}
            />
          </>
        );
      }}
    </RequireObjectPermissions>
  );
}
