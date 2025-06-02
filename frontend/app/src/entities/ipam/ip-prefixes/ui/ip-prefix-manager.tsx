import { IP_PREFIX_GENERIC } from "@/entities/ipam/constants";
import { IpPrefixTable, IpPrefixTableProps } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-table";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { ModelSchema } from "@/entities/schema/types";
import ErrorScreen from "@/shared/components/errors/error-screen";

export interface IpPrefixManagerProps {
  schema: ModelSchema;
  baseFilters?: IpPrefixTableProps["baseFilters"];
}

export function IpPrefixManager({ schema: prefixSchema, baseFilters }: IpPrefixManagerProps) {
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
