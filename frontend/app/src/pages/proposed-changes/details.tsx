import { Icon } from "@iconify-icon/react";
import { useAtom } from "jotai";
import { useEffect } from "react";
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
import type { ProposedChangeOutletContext } from "@/entities/proposed-changes/ui/use-proposed-change-outlet";
import { useSchema } from "@/entities/schema/ui/hooks/useSchema";

export function Component() {
  const { proposedChangeId } = useParams() as { proposedChangeId: string };
  const { schema } = useSchema(PROPOSED_CHANGES_OBJECT, { throwIfNotFound: true });
  const [, setProposedChange] = useAtom(proposedChangedState);

  const { isPending, error, data } = useGetProposedChangeDetails({ proposedChangeId });
  const proposedChangeData = data?.proposedChangeData;
  useTitle(
    `${proposedChangeData ? `${getNodeLabel(proposedChangeData)} - ` : ""}Proposed change - Infrahub`
  );

  useEffect(() => {
    if (proposedChangeData) {
      setProposedChange(proposedChangeData as ProposedChangeDetail);
    }
  }, [proposedChangeData, setProposedChange]);

  if (isPending) {
    return <LoadingIndicator className="h-full" />;
  }

  if (error || !data) {
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

  const { proposedChangeData: pc, metadata } = data;

  if (!pc.source_branch?.value) {
    return (
      <Content.Card>
        <Content.CardTitle title={getNodeLabel(pc)} />
        <NoDataFound message="Proposed change is missing a source branch." />
      </Content.Card>
    );
  }

  const sourceBranchValue = pc.source_branch.value;

  return (
    <Content.Card>
      <Content.CardTitle
        title={getNodeLabel(pc)}
        description={
          <div className="inline-flex items-center gap-1 text-xs">
            {metadata?.created_by ? (
              <Link
                to={getObjectDetailsUrl(metadata.created_by.__typename, metadata.created_by.id)}
                className="font-semibold text-custom-blue-green"
              >
                {getNodeLabel(metadata.created_by)}
              </Link>
            ) : null}
            wants to merge
            <Link to={constructPath(`/branches/${sourceBranchValue}`)}>
              <Badge variant="blue">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {sourceBranchValue}
              </Badge>
            </Link>
            into
            {/* destination_branch is conventionally always present; the optional
                chain reflects GraphQL nullability rather than a real data case. */}
            <Link to={constructPath(`/branches/${pc.destination_branch?.value}`)}>
              <Badge variant="green" className="items-center">
                <Icon icon="mdi:layers-triple" className="mr-1" />
                {pc.destination_branch?.value}
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

      <ProposedChangeTabs sourceBranch={sourceBranchValue} proposedChangeId={proposedChangeId} />

      <Outlet
        context={
          {
            proposedChangeData: pc,
            metadata,
            sourceBranch: sourceBranchValue,
          } satisfies ProposedChangeOutletContext
        }
      />
    </Content.Card>
  );
}
