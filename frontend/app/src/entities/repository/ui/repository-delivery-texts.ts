import type { DeliveryFailureCause } from "@/entities/repository/domain/model/delivery-state";

// The wording of the push state is provisional, so every text of the section lives in this file.
export const DELIVERY_TEXTS = {
  title: "Push to remote",
  status: "Status",
  cause: "Cause",
  requiredAction: "Required action",
  remoteMessage: "Message from the remote",
  pendingMerges: "Pending merges",
  nothingPending: "Nothing pending",
  importsPaused:
    "Imports from the remote default branch are paused until the pending pushes clear.",
} as const;

export const REQUIRED_ACTION_BY_CAUSE: Record<DeliveryFailureCause, string> = {
  "remote-unreachable": "Wait, or retry once the remote is reachable.",
  "remote-advanced": "Wait, or retry.",
  "record-failed": "Wait, or retry. The remote has the content.",
  "not-found": "Check the location, and that the credential can see the repository, then retry.",
  certificate: "Fix the certificate configuration, then retry.",
  credentials: "Fix the credential, then retry.",
  permission: "Grant push permission or lift the branch protection, then retry.",
  "import-interrupted":
    "Wait, or retry once the database and the remote are reachable. The remote has the content.",
  "import-failed": "Fix the content on the remote, then retry.",
  "replay-conflict": "Merge the source branch on the remote by hand, then retry. Or abandon.",
  "source-discarded": "Abandon.",
  "destination-rewritten": "Abandon.",
  unclassified: "Read the message, then retry or abandon.",
};
