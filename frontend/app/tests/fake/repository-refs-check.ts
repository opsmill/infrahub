import type { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import type { getRemoteCheckTaskFromApi } from "@/entities/repository/api/get-remote-check-task-from-api";

/** A check time earlier than the one the read-only commit log fixture reports. */
export const EARLIER_CHECKED_AT = "2025-03-10T18:00:00Z";

export const generateCheckRemoteRefsApiResult = (
  taskId: string
): Awaited<ReturnType<typeof checkRemoteRefsFromApi>> => ({
  data: { InfrahubReadOnlyRepositoryCheckRefs: { ok: true, task: { id: taskId } } },
});

/** `null` stands for a task the task manager does not list. */
export const generateRemoteCheckTaskApiResult = (
  state: "RUNNING" | "COMPLETED" | null
): Awaited<ReturnType<typeof getRemoteCheckTaskFromApi>> => ({
  data: { InfrahubTask: { edges: state === null ? [] : [{ node: { state } }] } },
});
