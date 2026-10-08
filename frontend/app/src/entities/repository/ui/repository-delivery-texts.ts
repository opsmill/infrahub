import type { DeliveryFailureCause } from "@/entities/repository/domain/model/delivery-state";

// The fixed texts of the push section and its menu items live here, so a change of wording touches one file.
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
  retry: "Retry push",
  retryStarted: "Retry of the pending pushes started.",
  retryFailed: "Error retrying the pending pushes:",
  abandon: "Abandon pending push",
  abandonMerges: "Abandon every pending merge of this repository:",
  abandonKeepsRemote: "Nothing is removed from the remote, and no remote branch is deleted.",
  abandonKeepsObjects:
    "Repository objects of the abandoned merges can stay on the default branch until the current commit is reimported.",
  abandonConfirm: "Abandon",
  abandonStarted: "Abandonment of the pending pushes started.",
  abandonFailed: "Error abandoning the pending pushes:",
  lastAbandonment: "Last abandonment",
  abandonedBy: "Abandoned by",
  abandonedMerges: "Abandoned merges",
  recordedCommit: "Recorded commit",
  repositoryObjects: "Repository objects",
  objectsCanStay: "The default branch can hold repository objects that the recorded commit lacks.",
  objectsCanLack:
    "The default branch can also lack repository objects that the recorded commit holds.",
  reimport: "Reimport current commit",
  reimportStarted: "Import of current commit started.",
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
