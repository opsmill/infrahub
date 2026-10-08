import type { checkRemoteRefsFromApi } from "@/entities/repository/api/check-remote-refs-from-api";
import type { getRunningRefsCheckFromApi } from "@/entities/repository/api/get-running-refs-check-from-api";
import type { RepositoryRemoteCheck } from "@/entities/repository/ui/repository-check-remote-button";

import { generatePermission } from "./permission";

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

export const generateRunningRefsCheckApiResult = (
  taskId: string | null
): Awaited<ReturnType<typeof getRunningRefsCheckFromApi>> => ({
  data: { InfrahubTask: { edges: taskId ? [{ node: { id: taskId } }] : [] } },
});
