import * as z from "zod";

export const DeliveryStatusSchema = z.enum(["none", "pending", "action-required"]);

export type DeliveryStatus = z.infer<typeof DeliveryStatusSchema>;

export const DeliveryFailureCauseSchema = z.enum([
  "remote-unreachable",
  "remote-advanced",
  "record-failed",
  "not-found",
  "certificate",
  "credentials",
  "permission",
  "import-interrupted",
  "import-failed",
  "replay-conflict",
  "source-discarded",
  "destination-rewritten",
  "unclassified",
]);

export type DeliveryFailureCause = z.infer<typeof DeliveryFailureCauseSchema>;

const PendingMergeSchema = z.object({
  entry_id: z.string(),
  source_branch: z.string(),
  source_commit: z.string(),
  merged_at: z.string(),
});

export type PendingMerge = z.infer<typeof PendingMergeSchema>;

export const DeliveryQueueSchema = z.object({
  format: z.literal(1),
  entries: z.array(PendingMergeSchema),
});

/** The push state of a repository, as the default branch holds it. */
export interface DeliveryState {
  status: DeliveryStatus;
  /** The labels and the color come from the backend, so the UI keeps the backend's wording. */
  statusLabel: string;
  statusColor: string | null;
  cause: DeliveryFailureCause | null;
  causeLabel: string | null;
  /** The message of the last failed push or import, with credentials removed. */
  error: string | null;
  /** In merge order. */
  pendingMerges: PendingMerge[];
}
