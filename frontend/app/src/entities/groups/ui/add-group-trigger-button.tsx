import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";
import { ButtonWithTooltip } from "@/shared/components/ui/button";

import type { GroupData } from "@/entities/groups/domain/types";
import { AddGroupForm } from "@/entities/groups/ui/add-group-form";
import { useGetObject } from "@/entities/nodes/object/ui/queries/get-object.query";
import { objectQueryKeys } from "@/entities/nodes/object/ui/queries/object.query-keys";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import type { Permission } from "@/entities/permission/types";
import type { ModelSchema } from "@/entities/schema/types";

interface AddGroupTriggerButtonProps {
  schema: ModelSchema;
  objectId: string;
  permission: Permission;
  currentGroups?: Array<GroupData>;
}

export function AddGroupTriggerButton({
  schema,
  currentGroups,
  objectId,
  permission,
}: AddGroupTriggerButtonProps) {
  const [isAddGroupFormOpen, setIsAddGroupFormOpen] = useState(false);

  const { data: objectDetailsData } = useGetObject({ objectSchema: schema, objectId });

  return (
    <>
      <ButtonWithTooltip
        onClick={() => setIsAddGroupFormOpen(true)}
        className="p-2"
        disabled={!permission.update.isAllowed}
        tooltipContent={permission.update.message ?? "Add groups"}
        tooltipEnabled
        data-testid="open-group-form-button"
      >
        <Icon icon="mdi:plus" className="text-lg" />
      </ButtonWithTooltip>

      <SlideOver
        offset={1}
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={objectDetailsData ? getNodeLabel(objectDetailsData) : ""}
            title="Select group(s)"
            subtitle="Select one or more groups to assign"
          />
        }
        open={isAddGroupFormOpen}
        setOpen={setIsAddGroupFormOpen}
      >
        <AddGroupForm
          objectId={objectId}
          defaultGroupIds={
            currentGroups
              ? {
                  source: { type: "user" },
                  value: currentGroups.map(({ id, display_label, __typename }) => ({
                    id,
                    display_label,
                    __typename,
                  })),
                }
              : undefined
          }
          schema={schema}
          className="p-4"
          onCancel={() => setIsAddGroupFormOpen(false)}
          onUpdateCompleted={async () => {
            await queryClient.invalidateQueries({ queryKey: objectQueryKeys.all });
            setIsAddGroupFormOpen(false);
          }}
        />
      </SlideOver>
    </>
  );
}
