import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { Link, Outlet, useParams } from "react-router";

import { queryClient } from "@/shared/api/rest/client";
import { constructPath } from "@/shared/api/rest/fetch";
import ErrorScreen from "@/shared/components/errors/error-screen";
import NoDataFound from "@/shared/components/errors/no-data-found";
import Content from "@/shared/components/layout/content";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { Badge } from "@/shared/components/ui/badge";
import { PROPOSED_CHANGES_OBJECT } from "@/shared/config/constants";
import { useTitle } from "@/shared/hooks/useTitle";

import { ObjectHelpButton } from "@/entities/nodes/object/ui/object-help-button";
import { getNodeLabel } from "@/entities/nodes/object/utils/get-node-label";
import { getObjectDetailsUrl } from "@/entities/nodes/utils";
import type { ProposedChangeDetail } from "@/entities/proposed-changes/domain/proposed-change.types";
import { proposedChangedState } from "@/entities/proposed-changes/stores/proposedChanges.atom";
import { useGetProposedChangeDetails } from "@/entities/proposed-changes/ui/queries/get-proposed-change-details.query";
import { ProposedChangeTabs } from "@/entities/proposed-changes/ui/tabs/proposed-change-tabs";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT, { throwIfNotFound: true });
  const [, setProposedChange] = useAtom(proposedChangedState);

  const { isPending, error, data } = useGetProposedChangeDetails({ proposedChangeId });
  useTitle(
    `${data?.proposedChangeData ? `${getNodeLabel(data.proposedChangeData)} - ` : ""}Proposed change - Infrahub`
  );

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  const { proposedChangeData, metadata } = data ?? {};

  if (error || !proposedChangeData) {
    return (
      <Content.Card>
        <Content.CardTitle
          title="Proposed changes"
          reload={() => {
            queryClient.invalidateQueries({
              predicate: (query) => query.queryKey.includes(proposedChangeId),
            });
          }}
          isReloadLoading={isPending}
          end={
            <ObjectHelpButton
              documentationUrl={schema.documentation}
              kind={PROPOSED_CHANGES_OBJECT}
              className="ml-auto"
            />
          }
        />

        {error ? (
          <ErrorScreen message={error.message} />
        ) : (
          <NoDataFound message="No proposed changes found." />
        )}
      </Content.Card>
    );
  }

  setProposedChange(proposedChangeData as ProposedChangeDetail);

  return (
    <Content.Card>
      <Content.CardTitle
        title={getNodeLabel(proposedChangeData)}
        description={
          <div className="inline-flex items-center gap-1 text-xs">
            <Link
              to={getObjectDetailsUrl(metadata?.created_by?.__typename!, metadata?.created_by?.id)}
              className="font-semibold text-custom-blue-green"
            >
              {metadata?.created_by ? getNodeLabel(metadata.created_by) : ""}
            </Link>
            wants to merge
            <Link to={constructPath(`/branches/${proposedChangeData.source_branch?.value}`)}>
              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.source_branch?.value}
              </Badge>
            </Link>
            into
            <Link to={constructPath(`/branches/${proposedChangeData.destination_branch?.value}`)}>
              <Badge variant="green" className="items-center">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {proposedChangeData.destination_branch?.value}
              </Badge>
            </Link>
          </div>
        }
        reload={() => {
          queryClient.invalidateQueries({
            predicate: (query) => query.queryKey.includes(proposedChangeId),
          });
        }}
        isReloadLoading={isPending}
        end={
          <ObjectHelpButton
            documentationUrl={schema?.documentation}
            kind={PROPOSED_CHANGES_OBJECT}
            className="ml-auto"
          />
        }
      />

      <ProposedChangeTabs
        sourceBranch={proposedChangeData.source_branch?.value!}
        proposedChangeId={proposedChangeId}
      />

      <Outlet />
    </Content.Card>
  );
}
