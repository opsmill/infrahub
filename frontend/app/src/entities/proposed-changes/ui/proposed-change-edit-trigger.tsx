import { gql } from "@apollo/client";
import { Icon } from "@iconify-icon/react";
import { useState } from "react";

import graphqlClient from "@/shared/api/graphql/graphqlClientApollo";
import useQuery from "@/shared/api/graphql/useQuery";
import { queryClient } from "@/shared/api/rest/client";
import SlideOver from "@/shared/components/display/slide-over";
import { ButtonWithTooltip } from "@/shared/components/ui/button";
import {
  PROPOSED_CHANGES_EDITABLE_STATE,
  PROPOSED_CHANGES_OBJECT,
} from "@/shared/config/constants";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { proposedChangesQueryKeys } from "@/entities/proposed-changes/ui/queries/proposed-changes.query-keys";
import { ProposedChangeEditForm } from "@/entities/proposed-changes/ui/proposed-change-edit-form";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

import { getObjectPermissionsQuery } from "../../permission/queries/getObjectPermissions";
import { getPermission } from "../../permission/utils";

export const ProposedChangeEditTrigger = ({
  proposedChangesDetails,
}: {
  proposedChangesDetails: any;
}) => {
  const { schema: proposedChangeSchema } = useSchema(PROPOSED_CHANGES_OBJECT);
  const [showEditDrawer, setShowEditDrawer] = useState(false);

  const { loading, data } = useQuery(gql(getObjectPermissionsQuery(PROPOSED_CHANGES_OBJECT)));

  const permission = getPermission(data?.[PROPOSED_CHANGES_OBJECT]?.permissions?.edges);

  return (
    <>
      <ButtonWithTooltip
        disabled={
          loading ||
          !permission.update.isAllowed ||
          !PROPOSED_CHANGES_EDITABLE_STATE.includes(proposedChangesDetails?.state?.value)
        }
        variant="outline"
        size="icon"
        tooltipEnabled={!permission.update.isAllowed}
        tooltipContent={permission.update.message ?? undefined}
        onClick={() => setShowEditDrawer(true)}
        data-testid="edit-button"
      >
        <Icon icon="mdi:pencil" aria-hidden="true" />
      </ButtonWithTooltip>

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
