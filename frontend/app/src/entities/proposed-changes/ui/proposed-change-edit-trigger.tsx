import { Icon } from "@iconify-icon/react";
import { Button } from "@infrahub/ui";
import { useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import { queryClient } from "@/shared/api/rest/client";
import { Tooltip } from "@/shared/components/aria/tooltip";
import SlideOver from "@/shared/components/display/slide-over";
import {
  PROPOSED_CHANGES_EDITABLE_STATE,
  PROPOSED_CHANGES_OBJECT,
} from "@/shared/config/constants";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { useGetObjectPermissions } from "@/entities/permission/ui/queries/get-object-permissions.query";
import { ProposedChangeEditForm } from "@/entities/proposed-changes/ui/proposed-change-edit-form";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export const ProposedChangeEditTrigger = ({
  proposedChangesDetails,
}: {
  proposedChangesDetails: any;
}) => {
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGES_OBJECT);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const { isPending, data: permission } = useGetObjectPermissions(PROPOSED_CHANGES_OBJECT);

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

      <SlideOver
        title={
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
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}
      >
        <ProposedChangeEditForm
          initialData={proposedChangesDetails}
          onSuccess={async () => {
            setShowEditDrawer(false);
            await graphqlClient.reFetchObservableQueries();
            await queryClient.invalidateQueries({ queryKey: proposedChangesQueryKeys.all });
          }}
        />
      </SlideOver>
    </>
  );
};
