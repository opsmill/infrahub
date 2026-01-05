import {
  IpPrefixTable,
  type IpPrefixTableProps,
} from "@/entities/ipam/ip-prefixes/ui/ip-prefix-table";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import type { ModelSchema } from "@/entities/schema/types";

export interface IpPrefixManagerProps {
  schema: ModelSchema;
  baseFilters?: IpPrefixTableProps["baseFilters"];
}

export function IpPrefixManager({ schema: prefixSchema, baseFilters }: IpPrefixManagerProps) {
  return (
    <ObjectTableProvider schema={prefixSchema}>
      <ObjectsManagerToolbar />
      <IpPrefixTable baseFilters={baseFilters} />
    </ObjectTableProvider>
  );
}
