import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import type { ColumnSurface } from "@/entities/nodes/columns/domain/model/column-surface";
import { ObjectTable } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import type { ModelSchema } from "@/entities/schema/domain/model/schema";

export interface ObjectsTableManagerProps {
  schema: ModelSchema;
  columnSurface?: ColumnSurface;
}

export function ObjectsManager({ schema, columnSurface }: ObjectsTableManagerProps) {
  const { isPending, error, data: permission } = useGetObjectPermissions(schema.kind!);

  if (isPending) return <LoadingIndicator className="h-page-body" />;

  if (error) return <ErrorScreen message={error.message} />;

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <ObjectTableProvider schema={schema} columnSurface={columnSurface} supportsColumnVisibility>
      <ObjectsManagerToolbar />
      <ObjectTable />
    </ObjectTableProvider>
  );
}
