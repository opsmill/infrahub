import { ACCOUNT_GENERIC_OBJECT } from "@/shared/config/constants";

import { ObjectTableProvider } from "@/entities/nodes/object/ui/object-table/object-table-context";
import { ObjectsManagerToolbar } from "@/entities/nodes/object/ui/objects-manager-toolbar";
import { AccountTable } from "@/entities/role-manager/ui/account-table";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { schema } = useSchema(ACCOUNT_GENERIC_OBJECT, { throwIfNotFound: true });

  return (
    <ObjectTableProvider schema={schema}>
      <ObjectsManagerToolbar />
      <AccountTable />
    </ObjectTableProvider>
  );
}
