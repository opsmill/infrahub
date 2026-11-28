import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { ACCOUNT_GENERIC_OBJECT } from "@/entities/role-manager/domain/model/account";
import {
  ACCOUNT_TABLE_ATTRIBUTES,
  ACCOUNT_TABLE_RELATIONSHIPS,
} from "@/entities/role-manager/domain/model/role-manager-table-fields";
import { RoleManagerObjectTable } from "@/entities/role-manager/ui/role-manager-object-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <RoleManagerObjectTable
        attributeNames={ACCOUNT_TABLE_ATTRIBUTES}
        relationshipNames={ACCOUNT_TABLE_RELATIONSHIPS}
        editRelationshipNames={["member_of_groups"]}
      />
    </ObjectTableProvider>
  );
}
