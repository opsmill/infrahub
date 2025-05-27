import { IP_ADDRESS_GENERIC } from "@/entities/ipam/constants";
import {
  IpAddressTable,
  IpAddressTableProps,
} from "@/entities/ipam/ip-addresses/ui/ip-address-table";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import React from "react";

export interface IpAddressManagerProps {
  schema: ModelSchema;
  baseFilters?: IpAddressTableProps["baseFilters"];
}

export function IpAddressManager({
  schema: ipAddressGenericSchema,
  baseFilters,
}: IpAddressManagerProps) {
  const ipAddressSchema = React.useMemo(() => {
    if (!isGenericSchema(ipAddressGenericSchema)) {
      return ipAddressGenericSchema;
    }
    if (ipAddressGenericSchema.used_by?.length === 1) {
      return getSchema(ipAddressGenericSchema.used_by[0]).schema;
    }
    return ipAddressGenericSchema;
  }, ipAddressGenericSchema?.used_by ?? []);

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
