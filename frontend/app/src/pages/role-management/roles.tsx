import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { ACCOUNT_ROLE_OBJECT } from "@/entities/role-manager/domain/model/account";
import {
  ROLE_TABLE_ATTRIBUTES,
  ROLE_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/domain/model/role-manager-table-fields";
import { RoleManagerObjectTable } from "@/entities/role-manager/ui/role-manager-object-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(ACCOUNT_ROLE_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <RoleManagerObjectTable
        attributeNames={ROLE_TABLE_ATTRIBUTES}
        relationshipNames={ROLE_TABLE_RELATIONSHIPS}
      />
    </ObjectTableProvider>
  );
}
