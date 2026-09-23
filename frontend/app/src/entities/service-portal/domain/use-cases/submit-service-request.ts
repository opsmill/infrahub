import { submitServiceRequestFromApi } from "@/entities/service-portal/api/submit-service-request-from-api";

export interface SubmitServiceRequestParams {
  entryId: string;
  // Create-input JSON of the entry's target kind, limited to the entry's allowlisted fields
  inputs: Record<string, unknown>;
}

export interface SubmitServiceRequestResult {
  requestId: string;
}

export const submitServiceRequest = async ({
  entryId,
  inputs,
}: SubmitServiceRequestParams): Promise<SubmitServiceRequestResult> => {
  const { data } = await submitServiceRequestFromApi({ entryId, inputs });
  const requestId = data.ServiceRequestSubmit?.request?.id;

  if (!requestId) {
    throw new Error("The request could not be submitted.");
  }

  return { requestId };
};
