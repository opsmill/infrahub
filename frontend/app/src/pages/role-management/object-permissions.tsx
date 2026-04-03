import { OBJECT_PERMISSION_OBJECT } from "@/shared/config/constants";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { ObjectPermissionTable } from "@/entities/role-manager/ui/object-permission-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(OBJECT_PERMISSION_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <ObjectPermissionTable />
    </ObjectTableProvider>
  );
}
