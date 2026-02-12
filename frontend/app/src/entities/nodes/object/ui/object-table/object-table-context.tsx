import { parseAsJson, parseAsString, useQueryStates } from "nuqs";
import React from "react";

import { QSP } from "@/shared/config/qsp";
import useFilters, { type Filter, FilterSchema } from "@/shared/hooks/useFilters";

import type { Permission } from "@/entities/permission/types";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import { getSchema } from "@/entities/schema/domain/get-schema";
import type { ModelSchema } from "@/entities/schema/types";
import { isGenericSchema } from "@/entities/schema/utils/is-generic-schema";

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
  const [, setFilters] = useFilters();
  const [{ filters, kind: kindInQsp }, setObjectTableQueryParams] = useQueryStates(
    {
      [QSP.KIND]: parseAsString,
      [QSP.FILTER]: parseAsJson(FilterSchema).withDefault([]),
    },
    { history: "push" }
  );

  React.useEffect(() => {
    if (!kindInQsp) return;
    if (window.location.pathname === "/schema") {
      // nuqs updates faster than React router QSP. If navigating to another route using "kind" QSP, it'll update it here 1st.
      return;
    }
    if (!isGenericSchema(schema) || !schema.used_by?.find((kind) => kind === kindInQsp)) {
      setObjectTableQueryParams({ kind: null });
    }
  }, [kindInQsp, schema.hash]);

  const selectedSchema = React.useMemo<ModelSchema>(() => {
    if (!isGenericSchema(schema)) return schema;

    if (schema.used_by?.length === 1) {
      const singleInheritingKind = schema.used_by[0] as string;
      const { schema: schemaOfSingleInheritingKind } = getSchema(singleInheritingKind);
      if (schemaOfSingleInheritingKind) return schemaOfSingleInheritingKind;
    }

    if (!kindInQsp) return schema;

    const inheritingKindInQsp = schema.used_by?.find((kind) => kind === kindInQsp);
    if (!inheritingKindInQsp) return schema;

    const { schema: schemaOfInheritingKindInQsp } = getSchema(inheritingKindInQsp);
    if (!schemaOfInheritingKindInQsp) return schema;

    return schemaOfInheritingKindInQsp;
  }, [kindInQsp, schema.hash]);

  return (
    <RequireObjectPermissions schema={schema}>
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
