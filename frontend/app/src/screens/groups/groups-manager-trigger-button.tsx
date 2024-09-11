import { ButtonProps, ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { usePermission } from "@/hooks/usePermission";
import { useState } from "react";
import { Icon } from "@iconify-icon/react";
import SlideOver, { SlideOverTitle } from "@/components/display/slide-over";
import { GroupsManager, GroupsManagerProps } from "@/screens/groups/groups-manager";
import { useObjectDetails } from "@/hooks/useObjectDetails";

type GroupsManagerTriggerProps = ButtonProps & GroupsManagerProps;

export const GroupsManagerTriggerButton = ({
  schema,
  objectId,
  ...props
}: GroupsManagerTriggerProps) => {
  const permission = usePermission();
  const [isManageGroupsDrawerOpen, setIsManageGroupsDrawerOpen] = useState(false);

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
        size="square"
        data-testid="manage-groups"
        {...props}>
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
        }>
        <GroupsManager schema={schema} objectId={objectId} className="p-4 overflow-auto" />
      </SlideOver>
    </>
  );
};
