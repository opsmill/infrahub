import { parseAsJson, parseAsString, useQueryStates } from "nuqs";
import React from "react";

import { QSP } from "@/shared/config/qsp";
import { uniqueItemsArray } from "@/shared/utils/array";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { OBJECT_COLUMN_SURFACE } from "@/entities/nodes/columns/domain/rules/column-surfaces";
import { type Filter, FilterSchema } from "@/entities/nodes/filters/domain/model/filter";
import type { Permission } from "@/entities/permission/domain/model/permission";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";
import { isGenericSchema } from "@/entities/schema/domain/rules/is-generic-schema";
import { getSchema } from "@/entities/schema/domain/use-cases/get-schema";

export type ObjectTableContextProps = {
  filters: Filter[];
  setFilters: (filters: Filter[]) => void;
  baseSchema: ModelSchema;
  selectedSchema: ModelSchema;
  permission: Permission;
  columnSurface: ColumnSurface;
  /**
   * Whether this table actually honours the column-visibility params. Only a table rendering
   * `DataTable` with a `columnVisibility` state does; the toolbar and the column headers are shared
   * with tables that render their own columns and would ignore a hide, so both controls ask here
   * before offering anything. Off unless a manager opts in.
   */
  supportsColumnVisibility: boolean;
};

export const ObjectTableContext = React.createContext<ObjectTableContextProps | null>(null);

export const ObjectTableProvider = ({
  children,
  schema,
  columnSurface = OBJECT_COLUMN_SURFACE,
  supportsColumnVisibility = false,
}: {
  children?: React.ReactNode;
  schema: ModelSchema;
  columnSurface?: ColumnSurface;
  supportsColumnVisibility?: boolean;
}) => {
  const [{ filters, kind: kindInQsp }, setObjectTableQueryParams] = useQueryStates(
    {
      [QSP.KIND]: parseAsString,
      [QSP.FILTER]: parseAsJson(FilterSchema).withDefault([]),
    },
    { history: "push" }
  );

  const setFilters = (newFilters: Filter[]) => {
    const cleanedFilters = uniqueItemsArray(newFilters, "name");
    setObjectTableQueryParams({
      filters: cleanedFilters.length ? cleanedFilters : null,
    });
  };

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
    <RequireObjectPermissions objectKind={schema.kind!}>
      {({ permission }) => {
        return (
          <ObjectTableContext
            value={{
              filters,
              setFilters,
              baseSchema: schema,
              selectedSchema,
              permission,
              columnSurface,
              supportsColumnVisibility,
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

/**
 * The column surface of the table this component sits in, falling back to the object surface.
 *
 * Non-throwing: a table cell may render outside any provider, and the object surface is the right
 * reading of "no table said otherwise".
 */
export function useColumnSurface(): ColumnSurface {
  return React.use(ObjectTableContext)?.columnSurface ?? OBJECT_COLUMN_SURFACE;
}

/**
 * Whether the table this component sits in honours the column-visibility params.
 *
 * Non-throwing: `false` is the correct reading both outside any provider and inside one that did
 * not opt in.
 */
export function useSupportsColumnVisibility(): boolean {
  return React.use(ObjectTableContext)?.supportsColumnVisibility ?? false;
}
