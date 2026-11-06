import ErrorScreen from "@/shared/components/errors/error-screen";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";

import { IpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";

export function Component() {
  const { parentSchema, parentData } = useCurrentFormContext();

  if (!parentSchema?.kind || !parentData) {
    return <ErrorScreen message="IP prefix not found" />;
  }

  return (
    <RequireObjectPermissions objectKind={parentSchema.kind}>
      {({ permission }) => (
        <IpPrefixTreeMap
          parentId={parentData.id}
          parentSchema={parentSchema}
          permission={permission}
        />
      )}
    </RequireObjectPermissions>
  );
}
