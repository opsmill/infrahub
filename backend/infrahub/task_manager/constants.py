from infrahub.core.constants import TaskConclusion

LOG_LEVEL_MAPPING = {10: "debug", 20: "info", 30: "warning", 40: "error", 50: "critical"}

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
