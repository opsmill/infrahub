import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { GLOBAL_PERMISSION_OBJECT } from "@/entities/permission/domain/model/permission";
import {
  GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES,
  GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/domain/model/role-manager-table-fields";
import { RoleManagerObjectTable } from "@/entities/role-manager/ui/role-manager-object-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(GLOBAL_PERMISSION_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <RoleManagerObjectTable
        attributeNames={GLOBAL_PERMISSIONS_TABLE_ATTRIBUTES}
        relationshipNames={GLOBAL_PERMISSIONS_TABLE_RELATIONSHIPS}
      />
    </ObjectTableProvider>
  );
}
