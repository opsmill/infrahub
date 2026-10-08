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
  version: z.number(),
  entries: z.array(PendingMergeSchema),
});

export const AbandonmentRecordSchema = z.object({
  format: z.literal(1),
  abandoned_at: z.string(),
  account_name: z.string(),
  /** The commit that the default branch kept. */
  recorded_commit: z.string(),
  /** An import that was still owed and was dropped with the pending merges. */
  import_owed_commit: z.string().nullish(),
  entries: z.array(PendingMergeSchema),
});

export type AbandonmentRecord = z.infer<typeof AbandonmentRecordSchema>;

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
  /** The version of the pending merges; an abandonment names it, so the backend refuses it once they change. */
  queueVersion: number;
  lastAbandonment: AbandonmentRecord | null;
}
