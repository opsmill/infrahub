import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { IpPrefixTable, IpPrefixTableProps } from "@/entities/ipam/prefixes/ui/ip-prefix-table";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { getSchema } from "@/entities/schema/domain/get-schema";
import { GenericSchema, ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";
import ErrorScreen from "@/shared/components/errors/error-screen";
import React from "react";

export interface IpPrefixManagerProps {
  schema: ModelSchema;
  baseFilters?: IpPrefixTableProps["baseFilters"];
}

export function IpPrefixManager({ schema, baseFilters }: IpPrefixManagerProps) {
  const prefixSchema = React.useMemo(
    () => {
      if (!isGenericSchema(schema)) return schema;
      if (schema.used_by?.length === 1) return getSchema(schema.used_by[0]).schema;
      return schema;
    },
    (schema as GenericSchema).used_by ?? []
  );

  if (!prefixSchema) {
    return <ErrorScreen message={`Schema ${IP_PREFIX_GENERIC} not found.`} />;
  }

  return (
    <RequireObjectPermissions objectKind={IP_PREFIX_GENERIC}>
      {({ permission }) => {
        return (
          <>
            <ObjectsManagerToolbar permission={permission} schema={prefixSchema} />
            <IpPrefixTable
              permission={permission}
              schema={prefixSchema}
              baseFilters={baseFilters}
            />
          </>
        );
      }}
    </RequireObjectPermissions>
  );
}
