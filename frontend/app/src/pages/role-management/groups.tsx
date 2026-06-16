import { ACCOUNT_GROUP_OBJECT } from "@/shared/config/constants";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { GroupTable } from "@/entities/role-manager/ui/group-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(ACCOUNT_GROUP_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <GroupTable />
    </ObjectTableProvider>
  );
}
