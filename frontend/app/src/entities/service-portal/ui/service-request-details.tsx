import { Card, CardContent, LinkButton, Spinner } from "@infrahub/ui";
import type { Query } from "@tanstack/react-query";

import ErrorScreen from "@/shared/components/errors/error-screen";
import { LoadingIndicator } from "@/shared/components/loading/loading-indicator";
import { QSP } from "@/shared/config/qsp";

import { getObjectDetailsUrl } from "@/entities/nodes/object/ui/routing/object-urls";
import { getProposedChangeDetailsUrl } from "@/entities/proposed-changes/ui/routing/proposed-change-urls";
import type { ServiceRequest } from "@/entities/service-portal/domain/model/service-request";
import { isServiceRequestInProgress } from "@/entities/service-portal/domain/rules/is-service-request-in-progress";
import { useGetServiceRequest } from "@/entities/service-portal/ui/queries/get-service-request.query";
import { ServiceRequestStatusBadge } from "@/entities/service-portal/ui/service-request-status-badge";

const pollWhileInProgress = (query: Query<ServiceRequest, Error, ServiceRequest, any>) =>
  isServiceRequestInProgress(query.state.data?.status) ? 5000 : false;

export function ServiceRequestDetails({ requestId }: { requestId: string }) {
  const {
    data: request,
    isPending,
    error,
  } = useGetServiceRequest({ requestId }, { refetchInterval: pollWhileInProgress });

  // The created service is linked on the request branch only, so it is read from there.
  const branch = request?.branch ?? undefined;
  const { data: requestOnBranch } = useGetServiceRequest(
    { requestId, branchName: branch },
    { enabled: !!branch, refetchInterval: pollWhileInProgress }
  );

  if (isPending) return <LoadingIndicator className="my-8" />;
  if (error) return <ErrorScreen message={error.message} />;

  const service = branch ? requestOnBranch?.service : null;

  return (
    <Card>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-semibold text-lg">{request.entryName ?? "Service request"}</h1>
          <ServiceRequestStatusBadge status={request.status} />
        </div>

        {request.message && <p className="text-neutral-700 text-sm">{request.message}</p>}

        {isServiceRequestInProgress(request.status) && (
          <div className="flex items-center gap-2 text-neutral-500 text-sm">
            <Spinner /> We're working on your request. This page updates automatically.
          </div>
        )}

        {(request.proposedChangeId || service) && (
          <div className="flex flex-wrap gap-2">
            {request.proposedChangeId && (
              <LinkButton
                variant="outline"
                size="sm"
                href={getProposedChangeDetailsUrl(request.proposedChangeId)}
              >
                View the proposed change
              </LinkButton>
            )}

            {service && branch && (
              <LinkButton
                variant="outline"
                size="sm"
                href={getObjectDetailsUrl(service.kind, service.id, [
                  { name: QSP.BRANCH, value: branch },
                ])}
              >
                Open your service
              </LinkButton>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
