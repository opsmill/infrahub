export const SERVICE_REQUEST_STATUS = {
  SUBMITTED: "submitted",
  GENERATING: "generating",
  FAILED: "failed",
  IN_REVIEW: "in_review",
  MERGED: "merged",
  REJECTED: "rejected",
} as const;

export type ServiceRequestStatus =
  (typeof SERVICE_REQUEST_STATUS)[keyof typeof SERVICE_REQUEST_STATUS];

export const isServiceRequestStatus = (value: unknown): value is ServiceRequestStatus =>
  Object.values<unknown>(SERVICE_REQUEST_STATUS).includes(value);

export interface ServiceRequest {
  id: string;
  status: ServiceRequestStatus | null;
  message: string | null;
  branch: string | null;
  entryName: string | null;
  proposedChangeId: string | null;
  // Only set when the request is read on its own branch
  service: { id: string; kind: string } | null;
}
