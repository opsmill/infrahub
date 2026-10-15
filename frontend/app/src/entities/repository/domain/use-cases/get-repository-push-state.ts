import {
  type GetRepositoryPushStateFromApiParams,
  getRepositoryPushStateFromApi,
} from "@/entities/repository/api/get-repository-push-state-from-api";
import {
  PendingMergeQueueSchema,
  PushFailureCauseSchema,
  PushStatusSchema,
  type RepositoryPushState,
} from "@/entities/repository/domain/model/repository-push-state";

export type GetRepositoryPushStateParams = GetRepositoryPushStateFromApiParams;

export type GetRepositoryPushStateResult = RepositoryPushState;

export type GetRepositoryPushState = (
  params: GetRepositoryPushStateParams
) => Promise<GetRepositoryPushStateResult>;

export const getRepositoryPushState: GetRepositoryPushState = async (params) => {
  const { data } = await getRepositoryPushStateFromApi(params);
  const repository = data.CoreRepository.edges[0]?.node;

  const queue = PendingMergeQueueSchema.nullish().safeParse(repository?.delivery_queue?.value);
  if (!queue.success) {
    throw new Error("Cannot read the pending pushes of this repository.");
  }

  // A value this page does not know still shows with the backend's label, and still asks the user to act.
  const status =
    PushStatusSchema.nullish().catch("action-required").parse(repository?.delivery_status?.value) ??
    "none";
  const cause =
    PushFailureCauseSchema.nullish()
      .catch("unclassified")
      .parse(repository?.delivery_failure_cause?.value) ?? null;

  return {
    status,
    statusLabel: repository?.delivery_status?.label ?? status,
    statusColor: repository?.delivery_status?.color ?? null,
    cause,
    causeLabel: repository?.delivery_failure_cause?.label ?? cause,
    error: repository?.delivery_error?.value ?? null,
    pendingMerges: queue.data?.entries ?? [],
  };
};
