import {
  IpPrefixTable,
  type IpPrefixTableProps,
} from "@/entities/ipam/ip-prefixes/ui/ip-prefix-table";
import { IP_PREFIX_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface IpPrefixManagerProps {
  schema: ModelSchema;
  baseFilters?: IpPrefixTableProps["baseFilters"];
}

export function IpPrefixManager({ schema: prefixSchema, baseFilters }: IpPrefixManagerProps) {
  return (
    <ObjectTableProvider schema={prefixSchema} columnSurface={IP_PREFIX_COLUMN_SURFACE}>
      <ObjectsManagerToolbar showColumnsPicker />
      <IpPrefixTable baseFilters={baseFilters} />
    </ObjectTableProvider>
  );
}
