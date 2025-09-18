import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { type ButtonProps, ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";

import { GroupsManager, type GroupsManagerProps } from "@/entities/groups/ui/groups-manager";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { Permission } from "@/entities/permission/types";

export interface GroupsManagerTriggerProps extends ButtonProps, GroupsManagerProps {
  permission: Permission;
}

export const GroupsManagerTriggerButton = ({
  schema,
  permission,
  objectId,
  ...props
}: GroupsManagerTriggerProps) => {
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);

  const { data: objectDetailsData } = useGetObject({ objectSchema: schema, objectId });

  return (
    <>
      <ButtonWithTooltip
        disabled={!permission.update.isAllowed}
        tooltipEnabled
        tooltipContent={permission.update.message ?? "Manage groups"}
        onClick={() => setIsManageGroupsDrawerOpen(true)}
        variant="outline"
        size="square"
        data-testid="manage-groups"
        {...props}
      >
        {props.children ?? <Icon icon="mdi:group" aria-hidden="true" />}
      </ButtonWithTooltip>

      <SlideOver
        open={isManageGroupsDrawerOpen}
        setOpen={setIsManageGroupsDrawerOpen}
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={objectDetailsData?.display_label}
            title="Manage groups"
            subtitle="Add and unassign groups"
          />
        }
      >
        <GroupsManager schema={schema} objectId={objectId} className="overflow-auto p-4" />
      </SlideOver>
    </>
  );
};
