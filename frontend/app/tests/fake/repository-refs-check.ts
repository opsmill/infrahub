import type { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import type { getRemoteCheckTaskFromApi } from "@/entities/repository/api/get-remote-check-task-from-api";
import type { RepositoryRemoteCheck } from "@/entities/repository/ui/repository-check-remote-button";

import { generatePermission } from "./permission";

/** A check time earlier than the one the read-only commit log fixture reports. */
export const EARLIER_CHECKED_AT = "2025-03-10T18:00:00Z";

export const generateRemoteCheck = (
  overrides: Partial<RepositoryRemoteCheck> = {}
): RepositoryRemoteCheck => ({
  objectKind: "CoreReadOnlyRepository",
  updatePermission: generatePermission().update,
  ...overrides,
});

export const generateCheckRemoteRefsApiResult = (
  taskId: string
): Awaited<ReturnType<typeof checkRemoteRefsFromApi>> => ({
  data: { InfrahubReadOnlyRepositoryCheckRefs: { ok: true, task: { id: taskId } } },
});

export const generateRemoteCheckTaskApiResult = ({
  isOngoing,
}: {
  isOngoing: boolean;
}): Awaited<ReturnType<typeof getRemoteCheckTaskFromApi>> => ({
  data: { InfrahubTask: { count: isOngoing ? 1 : 0 } },
});
