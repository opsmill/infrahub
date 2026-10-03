import ErrorScreen from "@/shared/components/errors/error-screen";
import { useCurrentFormContext } from "@/shared/components/form/utils/form-context";

import { getTreeMapParent } from "@/entities/ipam/ip-prefixes/domain/rules/get-tree-map-parent";
import { IpPrefixTreeMap } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map";
import { IpPrefixTreeMapEmptyState } from "@/entities/ipam/ip-prefixes/ui/ip-prefix-tree-map-empty-state";
import { RequireObjectPermissions } from "@/entities/permission/ui/require-object-permissions";

export function Component() {
  const { parentSchema, parentData } = useCurrentFormContext();

  if (!parentSchema?.kind || !parentData) {
    return <ErrorScreen message="IP prefix not found" />;
  }

  const parent = getTreeMapParent(parentData, parentSchema.kind);

  if (!parent) {
    return <ErrorScreen message={`${parentSchema.label} ${parentData.id} has no valid prefix`} />;
  }

  if (parent.memberType === "address") {
    return <IpPrefixTreeMapEmptyState utilization={parent.utilization} />;
  }

  return (
    <RequireObjectPermissions objectKind={parent.kind}>
      {({ permission }) => (
        <IpPrefixTreeMap parent={parent} parentSchema={parentSchema} permission={permission} />
      )}
    </RequireObjectPermissions>
  );
}
