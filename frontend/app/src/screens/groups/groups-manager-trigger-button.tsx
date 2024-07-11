import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { usePermission } from "@/hooks/usePermission";
import { useState } from "react";
import { useAtomValue } from "jotai/index";
import { currentBranchAtom } from "@/state/atoms/branches.atom";
import { Icon } from "@iconify-icon/react";
import SlideOver from "@/components/display/slide-over";
import { GroupsManager, GroupsManagerProps } from "@/screens/groups/groups-manager";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { Badge } from "@/components/ui/badge";

type GroupsManagerTriggerProps = ButtonProps & GroupsManagerProps;

export const GroupsManagerTriggerButton = ({
  schema,
  objectId,
  ...props
}: GroupsManagerTriggerProps) => {
  const permission = usePermission();
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);
  const currentBranch = useAtomValue(currentBranchAtom);

  const { data } = useObjectDetails(schema, objectId);

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

  return (
    <>
      <ButtonWithTooltip
        disabled={!permission.write.allow}
        tooltipEnabled
        tooltipContent={permission.write.message ?? "Manage groups"}
        onClick={() => setIsManageGroupsDrawerOpen(true)}
        variant="outline"
        size="icon"
        data-testid="manage-groups"
        {...props}>
        {props.children ?? <Icon icon="mdi:group" aria-hidden="true" />}
      </ButtonWithTooltip>

      <SlideOver
        open={isManageGroupsDrawerOpen}
        setOpen={setIsManageGroupsDrawerOpen}
        title={
          <div className="space-y-2">
            <div className="flex">
              <Badge variant="blue" className="flex items-center gap-1">
                <Icon icon="mdi:layers-triple" />
                <span>{currentBranch?.name}</span>
              </Badge>

              <ObjectHelpButton className="ml-auto" />
            </div>

            <div className="flex justify-between">
              <div className="text-sm flex items-center gap-2 whitespace-nowrap">
                {schema.label}

                <Icon icon="mdi:chevron-right" />

                <span className="truncate">{objectDetailsData?.display_label}</span>
              </div>
            </div>

            <div>
              <h3 className="text-lg font-semibold">Manage groups</h3>
              <p className="text-sm">Add and unassign groups</p>
            </div>
          </div>
        }>
        <GroupsManager schema={schema} objectId={objectId} className="p-4 overflow-auto" />
      </SlideOver>
    </>
  );
};
