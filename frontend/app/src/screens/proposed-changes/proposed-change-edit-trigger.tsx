import { usePermission } from "@/hooks/usePermission";
import { useSchema } from "@/hooks/useSchema";
import { PROPOSED_CHANGES_EDITABLE_STATE, PROPOSED_CHANGES_OBJECT } from "@/config/constants";
import React, { useState } from "react";
import { ButtonWithTooltip } from "@/components/buttons/button-primitive";
import { Icon } from "@iconify-icon/react";
import SlideOver from "@/components/display/slide-over";
import { ObjectHelpButton } from "@/components/menu/object-help-button";
import { ProposedChangeEditForm } from "@/screens/proposed-changes/form/proposed-change-edit-form";
import graphqlClient from "@/graphql/graphqlClientApollo";

export const ProposedChangeEditTrigger = ({
  proposedChangesDetails,
}: {
  proposedChangesDetails: any;
}) => {
  const permission = usePermission();
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGES_OBJECT);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  return (
    <>
      <ButtonWithTooltip
        disabled={
          !permission.write.allow ||
          !PROPOSED_CHANGES_EDITABLE_STATE.includes(proposedChangesDetails?.state?.value)
        }
        variant="outline"
        size="icon"
        tooltipEnabled={!permission.write.allow}
        tooltipContent={permission.write.message ?? undefined}
        onClick={() => setShowEditDrawer(true)}
        data-testid="edit-button">
        <Icon icon="mdi:pencil" aria-hidden="true" />
      </ButtonWithTooltip>

      <SlideOver
        title={
          <div className="space-y-2">
            <div className="flex justify-between overflow-hidden">
              <div className="flex-grow text-sm flex items-center gap-2 whitespace-nowrap truncate">
                <span>Proposed changes</span>
                <Icon icon="mdi:chevron-right" />
                <span className="truncate">{proposedChangesDetails?.display_label}</span>
              </div>

              <ObjectHelpButton
                kind={proposedChangeSchema?.label}
                documentationUrl={proposedChangeSchema?.documentation}
                className="shrink-0"
              />
            </div>

            <div>
              <h3 className="text-lg font-semibold">Edit Proposed change</h3>
            </div>
          </div>
        }
        open={showEditDrawer}
        setOpen={setShowEditDrawer}>
        <ProposedChangeEditForm
          initialData={proposedChangesDetails}
          onSuccess={async () => {
            setShowEditDrawer(false);
            await graphqlClient.reFetchObservableQueries();
          }}
        />
      </SlideOver>
    </>
  );
};
