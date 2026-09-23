import { useMutation } from "@tanstack/react-query";

import { submitServiceRequest } from "@/entities/service-portal/domain/use-cases/submit-service-request";

// invalidation-at-callsite: submitting creates a new request and touches no cached portal query;
// the caller navigates to the new request's page, which fetches it fresh.
export function useSubmitServiceRequest() {
  return useMutation({ mutationFn: submitServiceRequest });
}
