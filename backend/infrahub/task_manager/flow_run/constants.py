from infrahub.core.constants import TaskConclusion

LOG_LEVEL_MAPPING = {10: "debug", 20: "info", 30: "warning", 40: "error", 50: "critical"}

WEBHOOK_HTTP_ARTIFACT_KEY = "infrahub-webhook-http"
WEBHOOK_HTTP_ARTIFACT_TYPE = "result"

CONCLUSION_STATE_MAPPING: dict[str, TaskConclusion] = {
    "Scheduled": TaskConclusion.UNKNOWN,
    "Pending": TaskConclusion.UNKNOWN,
    "Running": TaskConclusion.UNKNOWN,
    "Completed": TaskConclusion.SUCCESS,
    "Failed": TaskConclusion.FAILURE,
    "Cancelled": TaskConclusion.FAILURE,
    "Crashed": TaskConclusion.FAILURE,
    "Paused": TaskConclusion.UNKNOWN,
    "Cancelling": TaskConclusion.FAILURE,
}
