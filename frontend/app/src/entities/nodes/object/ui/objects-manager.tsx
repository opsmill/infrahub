import ErrorScreen from "@/shared/components/errors/error-screen";
import UnauthorizedScreen from "@/shared/components/errors/unauthorized-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";

import { ObjectTable } from "@/entities/nodes/object/ui/object-table/object-table";
import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { useGetObjectPermissions } from "@/entities/permission/domain/get-object-permissions.query";
import type { ModelSchema } from "@/entities/schema/types";

export interface ObjectsTableManagerProps {
  schema: ModelSchema;
}

export function ObjectsManager({ schema }: ObjectsTableManagerProps) {
  const { isPending, error, data: permission } = useGetObjectPermissions(schema.kind as string);

  if (isPending) return <LoadingIndicator className="h-[calc(100vh-10.5rem)]" />;

  if (error) return <ErrorScreen message={error.message} />;

  if (!permission.view.isAllowed) {
    return <UnauthorizedScreen message={permission.view.message} />;
  }

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <ObjectTable />
    </ObjectTableProvider>
  );
}
