import { useRequiredParams } from "@/shared/hooks/use-required-params";

import { ServiceRequestDetails } from "@/entities/service-portal/ui/service-request-details";

export function Component() {
  const { requestId } = useRequiredParams("requestId");
  return <ServiceRequestDetails requestId={requestId} />;
}
