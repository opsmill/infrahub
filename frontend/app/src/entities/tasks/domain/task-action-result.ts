export interface TaskActionResult {
  taskId?: string;
}

interface TaskActionMutationPayload {
  ok?: boolean | null;
  task?: { id?: string | null } | null;
}

// Shared mapping for task-action mutations (retry, cancel): surface a GraphQL error,
// fail when the mutation did not succeed, otherwise return the resulting task id.
export const mapTaskActionResult = (
  payload: TaskActionMutationPayload | null | undefined,
  errors: ReadonlyArray<{ message: string }> | null | undefined,
  failureMessage: string
): TaskActionResult => {
  if (errors?.[0]?.message) {
    throw new Error(errors[0].message);
  }

  if (!payload?.ok) {
    throw new Error(failureMessage);
  }

  return {
    taskId: payload.task?.id ?? undefined,
  };
};
