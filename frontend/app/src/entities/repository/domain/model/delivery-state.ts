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
  entries: z.array(PendingMergeSchema),
});

/** The push state of a repository, as the default branch holds it. */
export interface DeliveryState {
  status: DeliveryStatus;
  /** The backend's own label and colour of the status, so its vocabulary stays authoritative. */
  statusLabel: string | null;
  statusColor: string | null;
  cause: DeliveryFailureCause | null;
  causeLabel: string | null;
  /** The remote's message of the last failed attempt, verbatim. */
  error: string | null;
  /** In merge order. */
  pendingMerges: PendingMerge[];
}
