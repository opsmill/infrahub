import React from "react";

import useFilters, { type Filter } from "@/shared/hooks/useFilters";

import { useSchemaSelectedInObjectTable } from "@/entities/nodes/object/ui/object-table/hooks/use-schema-selected-in-object-table";
import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/types";

export type ObjectTableContextProps = {
  filters: Filter[];
  setFilters: (filters: Filter[]) => void;
  baseSchema: ModelSchema;
  selectedSchema: ModelSchema;
  permission: Permission;
};

export const ObjectTableContext = React.createContext<ObjectTableContextProps | null>(null);

export const ObjectTableProvider = ({
  children,
  schema,
}: {
  children?: React.ReactNode;
  schema: ModelSchema;
}) => {
  const [filters, setFilters] = useFilters();
  const selectedSchema = useSchemaSelectedInObjectTable(schema);

  return (
    <RequireObjectPermissions objectKind={schema.kind as string}>
      {({ permission }) => {
        return (
          <ObjectTableContext
            value={{
              filters,
              setFilters,
              baseSchema: schema,
              selectedSchema,
              permission,
            }}
          >
            {children}
          </ObjectTableContext>
        );
      }}
    </RequireObjectPermissions>
  );
};

export function useObjectTableContext() {
  const context = React.use(ObjectTableContext);

  if (!context) {
    throw new Error("useObjectTableContext must be used within a ObjectTableProvider.");
  }

  return context;
}
