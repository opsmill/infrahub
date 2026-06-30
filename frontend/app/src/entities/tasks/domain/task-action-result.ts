export interface TaskActionResult {
  ok: boolean;
  taskId?: string;
}

interface TaskActionMutationPayload {
  ok?: boolean | null;
  task?: { id?: string | null } | null;
}

// Shared mapping for task-action mutations (retry, cancel): surface a GraphQL error,
// fail when the mutation returned no payload, otherwise normalise to a TaskActionResult.
export const mapTaskActionResult = (
  payload: TaskActionMutationPayload | null | undefined,
  errors: ReadonlyArray<{ message: string }> | null | undefined,
  failureMessage: string
): TaskActionResult => {
  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!payload) {
    throw new Error(failureMessage);
  }

  return {
    ok: payload.ok ?? false,
    taskId: payload.task?.id ?? undefined,
  };
};
