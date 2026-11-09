import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { GLOBAL_PERMISSION_OBJECT } from "@/entities/permission/domain/model/permission";
import { GlobalPermissionsTable } from "@/entities/role-manager/ui/global-permissions-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <GlobalPermissionsTable />
    </ObjectTableProvider>
  );
}
