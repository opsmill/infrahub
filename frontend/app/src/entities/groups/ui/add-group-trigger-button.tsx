import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { ButtonWithTooltip } from "@/shared/components/buttons/button-primitive";
import SlideOver, { SlideOverTitle } from "@/shared/components/display/slide-over";

import type { GroupDataFromAPI } from "@/entities/groups/api/types";
import AddGroupForm from "@/entities/groups/ui/add-group-form";
import { useGetObject } from "@/entities/nodes/object/domain/get-object.query";
import type { Permission } from "@/entities/permission/types";
import type { NodeSchema } from "@/entities/schema/types";

type AddGroupTriggerButtonProps = {
  schema: NodeSchema;
  objectId: string;
  permission: Permission;
  currentGroups?: Array<GroupDataFromAPI>;
};

export default function AddGroupTriggerButton({
  schema,
  currentGroups,
  objectId,
  permission,
  ...props
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
        {...props}
      >
        <Icon icon="mdi:plus" className="text-lg" />
      </ButtonWithTooltip>

      <SlideOver
        offset={1}
        title={
          <SlideOverTitle
            schema={schema}
            currentObjectLabel={objectDetailsData?.display_label}
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
            await graphqlClient.refetchQueries({ include: ["GET_GROUPS"] });
            setIsAddGroupFormOpen(false);
          }}
        />
      </SlideOver>
    </>
  );
}
