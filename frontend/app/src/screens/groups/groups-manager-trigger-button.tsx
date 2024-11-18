import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { useObjectDetails } from "@/hooks/useObjectDetails";
import { GroupsManager, GroupsManagerProps } from "@/screens/groups/groups-manager";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

type GroupsManagerTriggerProps = ButtonProps & GroupsManagerProps;

export const GroupsManagerTriggerButton = ({
  schema,
  permission,
  objectId,
  ...props
}: GroupsManagerTriggerProps) => {
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);

  const { data } = useObjectDetails(schema, objectId);

  const objectDetailsData = schema && data && data[schema.kind!]?.edges[0]?.node;

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
        <GroupsManager schema={schema} objectId={objectId} className="p-4 overflow-auto" />
      </SlideOver>
    </>
  );
};
