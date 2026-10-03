import ErrorScreen from "@/shared/components/errors/error-screen";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";

import { getTreeMapParent } from "@/entities/ipam/ip-prefixes/domain/rules/get-tree-map-parent";
import { IpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";

export function Component() {
  const { parentSchema, parentData } = useCurrentFormContext();

  if (!parentSchema?.kind || !parentData) {
    return <ErrorScreen message="IP prefix not found" />;
  }

  const kind = parentSchema.kind;
  const parent = getTreeMapParent(parentData, kind);

  if (!parent) {
    return <ErrorScreen message={`${parentSchema.label} ${parentData.id} has no valid prefix`} />;
  }

  return (
    <RequireObjectPermissions objectKind={kind}>
      {({ permission }) => (
        <IpPrefixTreeMap parent={parent} parentSchema={parentSchema} permission={permission} />
      )}
    </RequireObjectPermissions>
  );
}
