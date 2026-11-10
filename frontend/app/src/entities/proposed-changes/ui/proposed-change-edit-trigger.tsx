import { Button, Sheet, Tooltip } from "@infrahub/ui";
import { useState } from "react";

import { queryClient } from "@/shared/api/rest/client";
import { Icon } from "@/shared/components/display/icon";

import { getNodeLabel } from "@/entities/nodes/object/domain/rules/get-node-label";
import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { PROPOSED_CHANGE_OBJECT } from "@/entities/proposed-changes/domain/model/proposed-change";
import { PROPOSED_CHANGES_EDITABLE_STATE } from "@/entities/proposed-changes/domain/model/proposed-change-state";
import { ProposedChangeEditForm } from "@/entities/proposed-changes/ui/proposed-change-edit-form";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const ProposedChangeEditTrigger = ({
  proposedChangesDetails,
}: {
  proposedChangesDetails: any;
}) => {
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGE_OBJECT);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const { isPending, data: permission } = useGetObjectPermissions(PROPOSED_CHANGE_OBJECT);

  return (
    <>
      <Tooltip
        message={
          !permission?.update.isAllowed ? (permission?.update.message ?? undefined) : undefined
        }
      >
        <Button
          variant="outline"
          size="xs"
          shape="circle"
          isDisabled={
            isPending ||
            !permission?.update.isAllowed ||
            !PROPOSED_CHANGES_EDITABLE_STATE.includes(proposedChangesDetails?.state?.value)
          }
          isDisabledAndFocusable={!permission?.update.isAllowed}
          onPress={() => setShowEditDrawer(true)}
          data-testid="edit-button"
        >
          <Icon icon="mdi:pencil" aria-hidden="true" />
        </Button>
      </Tooltip>

      <Sheet isOpen={showEditDrawer} onOpenChange={setShowEditDrawer}>
        <div className="space-y-2">
          <div className="flex justify-between overflow-hidden">
            <div className="flex grow items-center gap-2 truncate whitespace-nowrap text-sm">
              <span>Proposed changes</span>
              <Icon icon="mdi:chevron-right" />
              <span className="truncate">
                {proposedChangesDetails ? getNodeLabel(proposedChangesDetails) : ""}
              </span>
            </div>

            <ObjectHelpButton
              kind={proposedChangeSchema?.label}
              documentationUrl={proposedChangeSchema?.documentation}
              className="shrink-0"
            />
          </div>

          <div>
            <h3 className="font-semibold text-lg">Edit Proposed change</h3>
          </div>
        </div>
        <ProposedChangeEditForm
          initialData={proposedChangesDetails}
          onSuccess={async () => {
            setShowEditDrawer(false);
            await queryClient.invalidateQueries({ queryKey: proposedChangesQueryKeys.all });
          }}
          onCancel={() => setShowEditDrawer(false)}
        />
      </Sheet>
    </>
  );
};
